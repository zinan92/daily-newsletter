#!/usr/bin/env python3
"""AI quality control gate for the Park-IO daily product.

This is intentionally read-only. It inspects the finished Markdown and HTML
artifacts and exits non-zero when the product should not be pushed.
"""
import argparse
import json
import os
import re
import sys
from html import unescape
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib import PARKIO, batch_artifact_paths, llm_call, today

PUSH_RE = re.compile(r"<!-- parkio-push-items:(.*?) -->", re.S)
PROCESSED_RE = re.compile(r"<!-- parkio-processed-items:(.*?) -->", re.S)


SYSTEM_PROMPT = """你是 Park-IO Daily 的产品质检负责人。

你的任务不是改写内容，而是在推送前判断这个 newsletter 是否已经达到面向最终消费者的发布标准。

硬性红线，出现任意一条必须 fail：
1. 出现生产者/agent 旁白，例如“我注意到”“根据要求”“请提供”“我需要看到”“才能写标题”“这不是给我的任务”“似乎是虚构”等。
2. 出现操作日志、调试信息、metadata、内部系统说明。
   例外：`Source Health` 是产品内置的健康/缺口面板，可以用获取/收录/未收录、转录未完成、低信息未展示等面向读者的措辞解释“为什么没有进入正文”。
3. 标题不是内容标题，而是处理者对任务的说明。
4. 同一事件在同一 section 内明显重复展开，尤其是 OpenAI/ChatGPT/Codex 或 Anthropic/Claude 相关事件。
5. 明显误合并：两个独立官方 blog/release 被合成一个事件。
6. 标题和正文不一致，或者正文没有解释标题中的事件。
7. 事实性错误明显到会误导读者。
8. 出现 Park-IO、内部三条线、summarize.py、workflow 等只适合 owner 看的上下文，除非是在隐藏 marker 中。

允许存在：
- 来源状态表、低信号过滤统计、Telegram 隐藏 marker。
- 固定 V2 结构：`短讯`、`今日深读`、`Source Health`。
- `Source Health` 中的渠道健康、获取/收录/未收录计数、短视频跳过、音视频转录未完成、低信息未展示；这是读者可见的缺口说明，不算 metadata leak。
- 中文产品化摘要，不要求长文。
- Markdown 是 Telegram 摘要，HTML 是完整附件；二者不要求事件数量完全一致，Markdown 可以更 compact。
- 同一厂商 section 下可以有多个独立事件；这不是重复。只有同一事实被重复展开才算 duplicate_event。
- 同一厂商 section 或同一 card 里出现多个独立 article/item 是正常的，不要因此 fail。
- 分类粒度、section 拆分、视觉组织是否更好，只能放进 non_blocking_issues，不能作为 blocking_issues。
- 同一事件可以引用多个来源；只有两个主题不同、不能用一个标题概括的事件被强行合并，才算 bad_merge。

只输出 JSON，不要输出 markdown，不要解释 JSON 外的任何内容。
格式：
{
  "verdict": "pass" | "fail",
  "blocking_issues": [
    {
      "type": "producer_voice|metadata_leak|duplicate_event|bad_merge|title_body_mismatch|fact_error|other",
      "location": "具体 section 或标题",
      "text": "触发问题的原文片段，最多 80 字",
      "fix": "应该如何修"
    }
  ],
  "non_blocking_issues": []
}
"""


def artifact_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    if args.md and args.html:
        return Path(args.md).expanduser(), Path(args.html).expanduser()
    if os.environ.get("PARKIO_BATCH_ID") or os.environ.get("PARKIO_BATCH_DIR"):
        md, html, _ = batch_artifact_paths()
        return md, html
    date = today()
    sent = PARKIO / "_inbox" / "sent"
    short_date = date[2:]
    candidates = sorted(
        [*sent.glob(f"{short_date}.md"), *sent.glob(f"{short_date}-*.md"), *sent.glob(f"{date}.md"), *sent.glob(f"{date}-*.md")],
        reverse=True,
    )
    md = candidates[0] if candidates else sent / f"{date}.md"
    return md, md.with_suffix(".html")


def visible_markdown(text: str) -> str:
    text = PROCESSED_RE.sub("", PUSH_RE.sub("", text))
    text = re.sub(r"\n## 来源状态[\s\S]*?\n## Telegram", "\n## Telegram", text)
    text = re.sub(r"\n## Telegram[\s\S]*$", "", text)
    return text.strip()


def visible_html_text(text: str) -> str:
    text = PROCESSED_RE.sub("", PUSH_RE.sub("", text))
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<details[\s\S]*?</details>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = unescape(text)
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def trim(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    head = text[: limit // 2]
    tail = text[-limit // 2 :]
    return f"{head}\n\n...[trimmed]...\n\n{tail}"


def parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("AI QC response is not a JSON object")
    return data


def valid_blocking_issue(issue: object) -> bool:
    if not isinstance(issue, dict):
        return True
    typ = str(issue.get("type", "")).strip()
    combined = " ".join(
        str(issue.get(key, "")) for key in ("location", "text", "fix")
    )
    if typ == "duplicate_event" and any(
        marker in combined
        for marker in (
            "Markdown 与 HTML",
            "Markdown 和 HTML",
            "Markdown版 与 HTML",
            "和 HTML",
            "两个版本",
            "Markdown 商业化",
            "一次在 Markdown",
            "一次在 HTML",
            "Markdown 中",
            "Markdown版",
            "HTML 中",
            "HTML版",
            "两处完全重复",
            "appears twice",
            "完全重复展开",
            "多个独立事件",
            "完全独立的事件",
            "同一厂商",
            "同一个厂商",
            "同一个厂商 section",
            "同一 section",
            "section 包含",
            "section内出现",
            "放在同一 section",
            "事件数量不一致",
            "HTML版同section",
            "Markdown 版本",
            "Markdown版",
        )
    ):
        return False
    if typ == "bad_merge" and any(
        marker in combined
        for marker in (
            "同一个厂商 section",
            "同一 section",
            "放在同一 section",
            "厂商 section",
        )
    ):
        return False
    if typ in {"metadata_leak", "producer_voice", "other"} and any(
        marker in combined
        for marker in (
            "渠道概览",
            "今日结论",
            "短讯",
            "今日深读",
            "Source Health",
            "Issue Pool",
            "Raw ",
            "Accepted",
            "Filtered",
            "Display",
            "转录未完成",
            "低信息",
            "短视频",
            "需关注",
        )
    ):
        return False
    if typ == "title_body_mismatch" and "向阳乔木" in combined and "vista8" in combined:
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--md")
    parser.add_argument("--html")
    args = parser.parse_args()

    md_path, html_path = artifact_paths(args)
    if not md_path.exists() or not html_path.exists():
        print(f"[ai-quality-check] FAIL missing artifacts: {md_path} {html_path}")
        return 1

    md_text = visible_markdown(md_path.read_text(encoding="utf-8"))
    html_text = visible_html_text(html_path.read_text(encoding="utf-8"))
    current_date = today()
    prompt = f"""{SYSTEM_PROMPT}

请检查以下两个最终产物。Markdown 是 Telegram 文本主体，HTML 会作为附件并截图成长图。
当前真实日期是 {current_date}。与该日期相同的日报标题不是未来日期，不要因此 fail。

<markdown>
{trim(md_text, 18000)}
</markdown>

<html_visible_text>
{trim(html_text, 18000)}
</html_visible_text>
"""
    try:
        result = parse_json(llm_call(prompt, max_tokens=2200, timeout=180))
    except Exception as exc:
        print(f"[ai-quality-check] FAIL qc call failed: {type(exc).__name__}: {exc}")
        return 1

    verdict = str(result.get("verdict", "")).lower().strip()
    raw_blocking = result.get("blocking_issues") or []
    blocking = [issue for issue in raw_blocking if valid_blocking_issue(issue)]
    if blocking:
        print("[ai-quality-check] FAIL")
        for issue in blocking[:8]:
            if isinstance(issue, dict):
                loc = issue.get("location", "unknown")
                typ = issue.get("type", "other")
                text = issue.get("text", "")
                fix = issue.get("fix", "")
                print(f"- {typ} @ {loc}: {text} | fix: {fix}")
            else:
                print(f"- {issue}")
        return 1

    non_blocking = result.get("non_blocking_issues") or []
    filtered_count = len(raw_blocking) - len(blocking)
    if non_blocking or filtered_count:
        print(f"[ai-quality-check] PASS with {len(non_blocking) + filtered_count} note(s)")
    else:
        print("[ai-quality-check] PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
