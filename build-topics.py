#!/usr/bin/env python3
"""Build an hourly, read-only topic workbench from pending raw inputs.

This script intentionally does NOT call open-batch, score, summarize, archive,
finalize, or send. It reads inbox/unprocessed and renders lightweight owner
views so topics can refresh hourly without consuming the daily digest batch.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from html import escape
from pathlib import Path

from lib import INBOX, UNPROCESSED_DIR, log, parse_frontmatter, parse_md_items

TOPICS_HTML = INBOX / "topics.html"
TOPICS_MD = INBOX / "topics.md"


def next_digest_time() -> str:
    now = datetime.now()
    target = now.replace(hour=8, minute=30, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target.strftime("%Y-%m-%d %H:%M")


def compact(text: str, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    # Transcript blocks are useful for the real digest, but too heavy for an
    # hourly topic board. Show only the leading substance.
    text = re.split(r"\bTranscript\b|### Transcript", text, maxsplit=1)[0].strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def channel_for_item(item: dict, fm: dict) -> str:
    url = (item.get("url") or "").lower()
    source = (item.get("source") or fm.get("profile_name") or fm.get("profile_id") or "").lower()
    category = (fm.get("category") or "").lower()
    profile = (fm.get("profile_id") or "").lower()
    if profile in {"openai", "anthropic"} or category == "ai-official" or any(
        token in source for token in ("openai", "chatgpt", "codex", "anthropic", "claude")
    ):
        return "official"
    if profile in {"x-saved", "manual-link"} or "personal-saved" in category or "wechat-manual" in category:
        return "manual"
    if "youtube.com/" in url or "youtu.be/" in url:
        return "youtube"
    if "douyin.com/" in url:
        return "douyin"
    if "mp.weixin.qq.com/" in url or "wechat" in category:
        return "wechat"
    if "x.com/" in url or "twitter.com/" in url or item.get("handle"):
        return "x"
    if "github.com/" in url or "rss" in category:
        return "rss"
    return "other"


CHANNELS = {
    "official": ("官方动态", "OpenAI / Anthropic / Claude / Codex"),
    "x": ("X 应用层", "长期关注账号的新增帖子"),
    "youtube": ("YouTube / Podcast", "视频、访谈、播客候选"),
    "douyin": ("抖音", "短视频候选"),
    "wechat": ("微信公众号", "自动 RSS / seed 公众号文章"),
    "manual": ("手动输入", "X 收藏、手动公众号和 manual-links"),
    "rss": ("RSS / GitHub", "非官方归类的 RSS 更新"),
    "other": ("其他", "未归类但仍在 pending batch 中"),
}


def collect_topics(inbox: Path = UNPROCESSED_DIR) -> list[dict]:
    rows: list[dict] = []
    if not inbox.exists():
        return rows
    for path in sorted(inbox.rglob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        fm, body = parse_frontmatter(text)
        for item in parse_md_items(body):
            source = item.get("source") or fm.get("profile_name") or fm.get("profile_id") or path.stem
            channel = channel_for_item(item, fm)
            rows.append(
                {
                    "title": compact(item.get("title") or "Untitled", 120),
                    "url": item.get("url", ""),
                    "source": source,
                    "profile": fm.get("profile_id") or path.stem,
                    "channel": channel,
                    "channel_label": CHANNELS.get(channel, CHANNELS["other"])[0],
                    "published": item.get("published") or fm.get("published_at") or "",
                    "excerpt": compact(item.get("content") or item.get("meta") or "", 260),
                    "file": path.name,
                    "mtime": path.stat().st_mtime,
                }
            )
    rows.sort(key=lambda row: (row["published"], row["mtime"], row["source"]), reverse=True)
    return rows


def grouped_topics(rows: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[row["channel"]].append(row)
    return groups


def render_md(rows: list[dict]) -> str:
    groups = grouped_topics(rows)
    lines = [
        "# Park-IO Topic Workbench",
        "",
        f"- 更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- Pending topics：{len(rows)}",
        f"- 下一次正式日报：{next_digest_time()}",
        "- 说明：这个文件只读 `inbox/unprocessed`，不消费 batch。",
        "",
    ]
    for key, (title, note) in CHANNELS.items():
        items = groups.get(key, [])
        if not items:
            continue
        lines.extend([f"## {title}", "", f"> {note} · {len(items)} 条", ""])
        for item in items:
            link = f"[{item['title']}]({item['url']})" if item["url"] else item["title"]
            meta = " · ".join(v for v in [item["source"], item["published"], item["file"]] if v)
            lines.append(f"- **{link}**")
            if meta:
                lines.append(f"  - {meta}")
            if item["excerpt"]:
                lines.append(f"  - {item['excerpt']}")
        lines.append("")
    if not rows:
        lines.append("当前没有 pending raw topics。")
    return "\n".join(lines).rstrip() + "\n"


def render_html(rows: list[dict]) -> str:
    groups = grouped_topics(rows)
    counts = Counter(row["channel"] for row in rows)
    chips = "".join(
        f"<span>{escape(CHANNELS[key][0])}<b>{counts.get(key, 0)}</b></span>"
        for key in CHANNELS
        if counts.get(key, 0)
    )
    sections = []
    for key, (title, note) in CHANNELS.items():
        items = groups.get(key, [])
        if not items:
            continue
        cards = []
        for item in items:
            title_html = escape(item["title"])
            if item["url"]:
                title_html = f'<a href="{escape(item["url"], quote=True)}">{title_html}</a>'
            cards.append(
                f"""
                <article class="topic">
                  <div class="meta">{escape(item["source"])} · {escape(item["published"] or "未标日期")}</div>
                  <h3>{title_html}</h3>
                  <p>{escape(item["excerpt"] or "暂无正文预览")}</p>
                  <div class="foot">{escape(item["file"])} · {escape(item["profile"])}</div>
                </article>
                """
            )
        sections.append(
            f"""
            <section>
              <header>
                <div>
                  <h2>{escape(title)}</h2>
                  <p>{escape(note)}</p>
                </div>
                <strong>{len(items)}</strong>
              </header>
              <div class="grid">{''.join(cards)}</div>
            </section>
            """
        )
    empty = "<section class='empty'>当前没有 pending raw topics。下一次 hourly fetch 后会自动刷新。</section>" if not rows else ""
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Park-IO Topic Workbench</title>
  <style>
    :root {{ color-scheme: light; --ink:#17211f; --muted:#66736f; --line:#dfe8e5; --bg:#f4f8f6; --card:#fff; --teal:#0f766e; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; color:var(--ink); background:var(--bg); }}
    main {{ max-width:1180px; margin:0 auto; padding:28px 18px 54px; }}
    .hero {{ display:flex; justify-content:space-between; gap:20px; align-items:flex-end; margin-bottom:20px; }}
    h1 {{ margin:0; font-size:28px; letter-spacing:0; }}
    .sub {{ margin:6px 0 0; color:var(--muted); }}
    .summary {{ display:flex; gap:10px; flex-wrap:wrap; margin:18px 0 28px; }}
    .summary span {{ border:1px solid var(--line); background:#fff; border-radius:999px; padding:7px 11px; color:#40504b; }}
    .summary b {{ margin-left:7px; color:var(--teal); }}
    section {{ background:var(--card); border:1px solid var(--line); border-radius:8px; padding:18px; margin:16px 0; }}
    section header {{ display:flex; justify-content:space-between; gap:16px; align-items:flex-start; border-bottom:1px solid var(--line); padding-bottom:12px; margin-bottom:14px; }}
    h2 {{ margin:0; font-size:20px; }}
    section header p {{ margin:4px 0 0; color:var(--muted); }}
    section header strong {{ color:var(--teal); font-size:30px; line-height:1; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:12px; }}
    .topic {{ border:1px solid #e7eeeb; border-radius:8px; padding:13px 14px; background:#fbfdfc; }}
    .topic h3 {{ margin:5px 0 8px; font-size:16px; line-height:1.35; }}
    .topic a {{ color:#0f5f7a; text-decoration:none; }}
    .topic a:hover {{ text-decoration:underline; }}
    .topic p {{ margin:0; color:#2e3d39; }}
    .meta,.foot {{ font-size:12px; color:var(--muted); }}
    .foot {{ margin-top:10px; }}
    .empty {{ color:var(--muted); }}
    @media (max-width: 720px) {{ .hero {{ display:block; }} h1 {{ font-size:24px; }} }}
  </style>
</head>
<body>
<main>
  <div class="hero">
    <div>
      <h1>Park-IO Topic Workbench</h1>
      <p class="sub">只读当前 unprocessed；用于小时级选题观察，不消费每日 batch。</p>
    </div>
    <p class="sub">更新：{datetime.now().strftime('%Y-%m-%d %H:%M')}<br>下一次正式日报：{next_digest_time()}</p>
  </div>
  <div class="summary"><span>Pending topics<b>{len(rows)}</b></span>{chips}</div>
  {''.join(sections)}
  {empty}
</main>
</body>
</html>
"""


def main() -> int:
    rows = collect_topics()
    INBOX.mkdir(parents=True, exist_ok=True)
    TOPICS_MD.write_text(render_md(rows), encoding="utf-8")
    TOPICS_HTML.write_text(render_html(rows), encoding="utf-8")
    log("build-topics", f"DONE — {len(rows)} pending topic(s) -> {TOPICS_HTML}")
    print(TOPICS_HTML)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
