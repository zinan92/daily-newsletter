#!/usr/bin/env python3
"""Pre-push quality checks for the Park-IO daily product."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from html import unescape

from lib import PARKIO, batch_artifact_paths, today

PUSH_RE = re.compile(r"<!-- parkio-push-items:(.*?) -->", re.S)
PROCESSED_RE = re.compile(r"<!-- parkio-processed-items:(.*?) -->", re.S)
NUMBERED_EVENT_RE = re.compile(r"^\d+\.\s+(.+)$")
URL_RE = re.compile(r"https?://[^\s)\"<>]+")
BOLD_LINK_RE = re.compile(r"^\*\*[^：:]{1,12}[：:]\[([^\]]+)\]\([^)]+\)\*\*$")
BAD_PATTERNS = (
    "我是 Claude Code",
    "我不能处理",
    "我注意到你",
    "我注意到您",
    "我注意到这条",
    "我注意到这不是给我的任务指令",
    "您的请求",
    "你的请求",
    "创意写作任务",
    "不在我的专业范围",
    "根据要求，我来改写",
    "我来改写这条信息",
    "根据你的要求",
    "根据这条信息",
    "为您准备以下摘要",
    "我需要指出",
    "不应该拒绝",
    "似乎是虚构",
    "信息似乎是虚构",
    "远在未来",
    "不会发布 Anthropic",
    "不会发布Anthropic",
    "这条更新值得看",
    "这条信息值得看",
    "高价值内容值得看",
    "这类短更新适合",
    "标题显示，这期主要围绕",
    "时长：未知",
    "转录排队",
    "字幕不可用",
    "仅标题更新",
    "字幕文本质量",
    "重新处理",
    "无法准确理解",
    "处理状态",
    "metadata",
    "已完成摘要",
    "已完成字幕摘要",
    "字幕摘要",
    "没有摘要的内容",
    "今天的行动线索",
    "把它当成今天的行动线索",
    "相互矛盾",
    "摘要如下",
    "内容似乎被截断",
    "undefined",
    "None",
    "null",
    "核心信息是：。",
    "我需要看到 Twitter",
    "我需要看到Twitter",
    "我需要看到实际",
    "需要看到实际",
    "才能为其写标题",
    "才能写标题",
    "撰写标题",
    "请提供 Twitter/X",
    "请提供Twitter/X",
    "请提供完整的推文",
    "字数统计",
    "符合你的要求",
    "Park-IO 的 Agent",
    "Park-IO的agent",
    "Park-IO的 Agent",
    "Line 1",
    "Line 2",
    "Line 3",
    "内容策划",
    "对这个产品产品线",
    "我们的三条线",
    "引用内容：",
    "文章标题：",
    "WeChat ID：",
    "WeChat ID:",
    "公众号：",
    "作者：",
    "https://t.co/",
    "应指",
    "应该指",
    "应该是指",
    "Anthropic 的 Codex",
    "Anthropic Codex",
    "Anthropic 发布的 Codex",
    "Anthropic 发布 Codex",
    "...",
)
METADATA_PATTERNS = (
    "来源配置：sources.md",
    "来源：sources.md",
    "Markdown 同步文件",
    "workflow.html",
    "inbox-workflow",
    "parkio-processed-items",
    "parkio-push-items",
    "source-health.json",
    "media-queue.json",
    "source_name",
    "profile_id",
    "内容线",
    "产品线",
    "tags",
)


def fail(msg: str, failures: list[str]) -> None:
    failures.append(msg)


def extract_push_items(text: str) -> list[str]:
    match = PUSH_RE.search(text)
    if not match:
        return []
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []
    return [str(item) for item in data if str(item).strip()]


def event_headings(text: str) -> list[str]:
    headings = []
    for line in text.splitlines():
        if line.startswith("##### "):
            headings.append(line.strip("# ").strip())
            continue
        match = NUMBERED_EVENT_RE.match(line.strip())
        if match:
            headings.append(match.group(1).strip())
            continue
        match = BOLD_LINK_RE.match(line.strip())
        if match:
            headings.append(match.group(1).strip())
    return headings


def visible_markdown(text: str) -> str:
    text = PROCESSED_RE.sub("", PUSH_RE.sub("", text))
    return text


def visible_html_text(text: str) -> str:
    text = PROCESSED_RE.sub("", PUSH_RE.sub("", text))
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<details[\s\S]*?</details>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "\n", text)
    return unescape(text)


def normalized_heading(value: str) -> str:
    value = re.sub(r"\[[^\]]+\]\([^)]+\)", "", value)
    value = re.sub(r"^[#\d.\s]+", "", value)
    return re.sub(r"\W+", "", value.lower()).strip()


def duplicate_visible_urls(*texts: str) -> list[str]:
    urls: list[str] = []
    for text in texts:
        urls.extend(URL_RE.findall(text))
    cleaned = [u.rstrip("。.,，;；") for u in urls]
    ignored_prefixes = (
        "http://localhost",
        "https://localhost",
    )
    candidates = [u for u in cleaned if not u.startswith(ignored_prefixes)]
    return sorted({u for u in candidates if candidates.count(u) > 1})


ENGLISH_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]+")


def raw_english_body_lines(visible_md: str) -> list[str]:
    """Body prose lines that are raw English with no Chinese (gotcha #5).

    The consumer newsletter is Chinese. A body line carrying >=6 English words
    and no Chinese character is un-rewritten source text. Markdown link labels
    and URLs are stripped first (reference links may legitimately quote an
    English X title); headings are checked elsewhere.
    """
    offenders: list[str] = []
    for line in visible_md.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        stripped = re.sub(r"\[[^\]]*\]\([^)]*\)", "", s)
        stripped = re.sub(r"https?://\S+", "", stripped)
        stripped = stripped.strip(" *_-：:·")
        if not stripped or re.search(r"[一-鿿]", stripped):
            continue
        if len(ENGLISH_WORD_RE.findall(stripped)) >= 6:
            offenders.append(s[:80])
    return offenders


def main() -> int:
    date = today()
    if os.environ.get("PARKIO_BATCH_ID") or os.environ.get("PARKIO_BATCH_DIR"):
        md, html, _ = batch_artifact_paths()
    else:
        sent = PARKIO / "inbox" / "sent"
        short_date = date[2:]
        candidates = sorted(
            [*sent.glob(f"{short_date}.md"), *sent.glob(f"{short_date}-*.md"), *sent.glob(f"{date}.md"), *sent.glob(f"{date}-*.md")],
            reverse=True,
        )
        md = candidates[0] if candidates else sent / f"{date}.md"
        html = md.with_suffix(".html")
    failures: list[str] = []
    warnings: list[str] = []

    if not md.exists():
        fail(f"missing markdown panel: {md}", failures)
    if not html.exists():
        fail(f"missing html panel: {html}", failures)
    if failures:
        for msg in failures:
            print(f"[quality-check] FAIL {msg}")
        return 1

    text = md.read_text(encoding="utf-8")
    html_text = html.read_text(encoding="utf-8")
    visible_md = visible_markdown(text)
    visible_html = visible_html_text(html_text)

    for pattern in BAD_PATTERNS:
        if pattern in visible_md or pattern in visible_html:
            fail(f"bad pattern found: {pattern}", failures)
    for pattern in METADATA_PATTERNS:
        if pattern in visible_md or pattern in visible_html:
            fail(f"metadata leaked into visible product: {pattern}", failures)

    english_lines = raw_english_body_lines(visible_md)
    if english_lines:
        fail(f"raw English in consumer body (not rewritten to Chinese): {english_lines[:2]}", failures)

    required_sections = ("## 今日精选",)
    for section in required_sections:
        if section not in text:
            fail(f"missing section: {section}", failures)

    has_media_updates = "## Podcast / YouTube / 抖音" in text
    if "### 厂商动态" not in text and "### 应用层实践" not in text and "### 我的收藏" not in text and not has_media_updates:
        warnings.append("missing product layer section")

    headings = event_headings(text)
    if not headings and not has_media_updates:
        warnings.append("no event headings found")
    normalized = [normalized_heading(h) for h in headings]
    duplicates = sorted({h for h in normalized if normalized.count(h) > 1 and h})
    if duplicates:
        fail(f"duplicate event headings: {duplicates[:3]}", failures)

    repeated_md_urls = duplicate_visible_urls(visible_md)
    if repeated_md_urls:
        warnings.append(f"duplicate visible markdown URLs: {repeated_md_urls[:3]}")
    repeated_html_urls = duplicate_visible_urls(visible_html)
    if repeated_html_urls:
        warnings.append(f"duplicate visible html URLs: {repeated_html_urls[:3]}")

    push_items = extract_push_items(text)
    if not push_items:
        warnings.append("no push marker URLs")
    if len(push_items) > 10:
        warnings.append(f"too many push URLs: {len(push_items)}")
    if len(set(push_items)) != len(push_items):
        fail("duplicate push URLs", failures)

    if "file:///Users/" in text:
        fail("local file URL leaked into telegram markdown", failures)
    if len(text) > 30000:
        warnings.append(f"markdown panel is large: {len(text)} chars")

    for msg in warnings:
        print(f"[quality-check] WARN {msg}")
    if failures:
        for msg in failures:
            print(f"[quality-check] FAIL {msg}")
        return 1
    if os.environ.get("PARKIO_SKIP_AI_QUALITY") != "1":
        ai = subprocess.run(
            [sys.executable, str(Path(__file__).parent / "ai-quality-check.py")],
            capture_output=True,
            text=True,
        )
        if ai.stdout.strip():
            print(ai.stdout.strip())
        if ai.stderr.strip():
            print(ai.stderr.strip(), file=sys.stderr)
        if ai.returncode != 0:
            if os.environ.get("PARKIO_STRICT_AI_QUALITY") == "1":
                return ai.returncode
            print(f"[quality-check] WARN AI quality check failed non-blocking: exit={ai.returncode}")
    print(f"[quality-check] PASS {date}: {len(headings)} events, {len(push_items)} push URLs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
