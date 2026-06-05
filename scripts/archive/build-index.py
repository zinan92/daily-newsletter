#!/usr/bin/env python3
"""
build-index.py — Generate the 慢学 AI profile index.
table of contents for the 113-video corpus.

Sections:
  1. Header — counts, date range
  2. 系列阅读 — videos grouped by《paper-title》, sorted by part number
  3. 按主题 — top tags with counts
  4. 全部按时间倒序 — chronological table

Reads from each video's .md frontmatter-equivalent header to extract:
  date, title, tags, douyin-source-url, relative .md path
"""
import re
import urllib.parse
from collections import defaultdict
from pathlib import Path

LIBRARY = Path.home() / "park-io" / "library" / "profiles" / "manxue-ai" / "items"
POST_ROOT = LIBRARY
OUTPUT = Path.home() / "park-io" / "outbox" / "library-maintenance" / "manxue-ai" / "douyin-index.md"

CIRCLED_DIGITS = {
    "①": 1, "②": 2, "③": 3, "④": 4, "⑤": 5,
    "⑥": 6, "⑦": 7, "⑧": 8, "⑨": 9, "⑩": 10,
    "⑪": 11, "⑫": 12, "⑬": 13, "⑭": 14, "⑮": 15,
}


def parse_video_md(path: Path) -> dict:
    """Extract metadata from a video .md. Returns dict with keys:
    date, title, tags, source_url, paper, part, rel_path."""
    text = path.read_text(encoding="utf-8")

    # Title: first non-empty H1 line
    title_m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    title = title_m.group(1).strip() if title_m else path.stem

    # Date: from `> 日期: 2026-XX-XX |` line
    date_m = re.search(r"日期:\s*(\d{4}-\d{2}-\d{2})", text)
    date = date_m.group(1) if date_m else ""

    # Source URL: douyin share link from `> Date: ... | 来源: <url>`
    src_m = re.search(r"来源:\s*(\S+)", text)
    source_url = src_m.group(1) if src_m else ""

    # Tags: from **标签:** #a, #b, #c line
    tags_m = re.search(r"\*\*标签:\*\*\s*(.+)$", text, re.MULTILINE)
    tags = []
    if tags_m:
        tags = [t.strip() for t in tags_m.group(1).split(",") if t.strip()]

    # Series detection: extract《paper-title》 from title (first occurrence)
    paper_m = re.search(r"《([^》]+)》", title)
    paper = paper_m.group(1).strip() if paper_m else ""
    # Part number: circled digit immediately after 》
    part = 0
    if paper_m:
        after = title[paper_m.end() : paper_m.end() + 2]
        for ch, n in CIRCLED_DIGITS.items():
            if ch in after:
                part = n
                break

    rel_path = path.relative_to(LIBRARY)

    return {
        "date": date,
        "title": title,
        "tags": tags,
        "source_url": source_url,
        "paper": paper,
        "part": part,
        "rel_path": str(rel_path),
        "stem": path.parent.name,
    }


def md_link(text: str, target: str) -> str:
    """Markdown link with URL-encoded target (handles Chinese/spaces)."""
    return f"[{text}]({urllib.parse.quote(target, safe='/')})"


def short_title(title: str, limit: int = 80) -> str:
    """Trim title for table display, removing tags and post-numeral fluff."""
    # Strip everything after first hashtag/newline cluster
    title = re.split(r"\s+#", title)[0]
    title = title.split("\n")[0]
    if len(title) > limit:
        title = title[:limit].rstrip() + "…"
    return title.strip()


def main() -> None:
    md_files = sorted(POST_ROOT.rglob("*.md"))
    videos = [parse_video_md(m) for m in md_files]
    videos.sort(key=lambda v: v["date"], reverse=True)

    # Date range
    dates = [v["date"] for v in videos if v["date"]]
    date_min, date_max = (min(dates), max(dates)) if dates else ("", "")

    # Group by paper (series)
    by_paper: dict = defaultdict(list)
    for v in videos:
        if v["paper"]:
            by_paper[v["paper"]].append(v)
    # Filter to true series (≥2 parts) and sort by part number
    series = [
        (paper, sorted(items, key=lambda x: (x["part"], x["date"])))
        for paper, items in by_paper.items()
        if len(items) >= 2
    ]
    series.sort(key=lambda kv: -len(kv[1]))

    # Top tags
    tag_counts: dict = defaultdict(int)
    for v in videos:
        for t in v["tags"]:
            tag_counts[t] += 1
    top_tags = sorted(tag_counts.items(), key=lambda kv: -kv[1])[:20]

    # Build INDEX.md
    lines: list = [
        "# 慢学AI · Corpus Index",
        "",
        f"> **{len(videos)} 篇** 视频转录 · 时间跨度 **{date_min} → {date_max}**  ",
        "> 全部 polish 完成（verbatim 中文段落） · 已修正系统性 ASR 错误（Cloud→Claude、慢学AI 同音字等）",
        "",
        "## 目录",
        "",
        "- [系列阅读](#系列阅读) — 按论文/书目成系列的视频",
        "- [按主题](#按主题) — 顶级 tag",
        "- [全部按时间倒序](#全部按时间倒序) — 完整列表",
        "",
        "---",
        "",
        "## 系列阅读",
        "",
    ]

    if not series:
        lines.append("_（未检测到 ≥2 篇的系列）_\n")
    for paper, items in series:
        lines.append(f"### 精读《{paper}》({len(items)} 篇)")
        lines.append("")
        for v in items:
            part_label = (
                next((c for c, n in CIRCLED_DIGITS.items() if n == v["part"]), "")
                if v["part"]
                else ""
            )
            link = md_link(short_title(v["title"], 70), v["rel_path"])
            date_part = v["date"] or "????-??-??"
            lines.append(f"- {part_label or '·'} {date_part} — {link}")
        lines.append("")

    lines.extend(
        [
            "---",
            "",
            "## 按主题",
            "",
            "| Tag | 篇数 |",
            "|---|---|",
        ]
    )
    for tag, c in top_tags:
        lines.append(f"| `{tag}` | {c} |")
    lines.append("")

    lines.extend(
        [
            "---",
            "",
            "## 全部按时间倒序",
            "",
            f"共 **{len(videos)}** 篇。",
            "",
            "| 日期 | 标题 | 主要 Tag |",
            "|---|---|---|",
        ]
    )
    for v in videos:
        link = md_link(short_title(v["title"], 90), v["rel_path"])
        primary_tags = " ".join(v["tags"][:3])
        date = v["date"] or "??"
        lines.append(f"| {date} | {link} | {primary_tags} |")
    lines.append("")
    lines.extend(
        [
            "---",
            "",
            "_自动生成于 corpus build。重新生成：`python3 ~/work/input-to-park/build-index.py`_",
        ]
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT}")
    print(f"  Total videos: {len(videos)}")
    print(f"  Series found: {len(series)}")
    print(f"  Top tags:     {len(top_tags)}")
    print(f"  File size:    {OUTPUT.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
