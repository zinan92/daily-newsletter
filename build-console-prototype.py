#!/usr/bin/env python3
"""Build the local Park-IO Inbox Console from the latest digest artifacts.

The console is a reader/owner shell around the newsletter. The newsletter
Markdown remains the source of truth; this script reads the generated Markdown,
HTML, and run-report for the current batch and avoids hard-coded daily copy.
"""

from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path


PARKIO = Path(os.environ.get("PARKIO_DIR", "/Users/wendy/park-io"))
INBOX = PARKIO / "_inbox"
PROCESSED = INBOX / "processed"
OUT = INBOX / "park-io-console-prototype.html"


def batch_label_from_id(batch_id: str | None) -> str | None:
    if not batch_id:
        return None
    raw = batch_id.strip()
    if re.fullmatch(r"\d{8}", raw):
        return f"{raw[2:4]}-{raw[4:6]}-{raw[6:8]}"
    if re.fullmatch(r"\d{2}-\d{2}-\d{2}", raw):
        return raw
    return raw


def latest_batch_dir() -> Path:
    requested = batch_label_from_id(os.environ.get("PARKIO_BATCH_ID"))
    if requested:
        path = PROCESSED / requested
        if path.exists():
            return path
    batches = [p for p in PROCESSED.glob("??-??-??") if p.is_dir()]
    if not batches:
        raise SystemExit(f"No processed batch directory found under {PROCESSED}")
    return sorted(batches, key=lambda p: p.name)[-1]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def section_lines(md: str, heading: str, stop_prefixes: tuple[str, ...]) -> list[str]:
    lines = md.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == heading:
            start = i + 1
            break
    if start is None:
        return []
    out: list[str] = []
    for line in lines[start:]:
        if any(line.startswith(prefix) for prefix in stop_prefixes):
            break
        if line.strip().startswith("<!--"):
            continue
        out.append(line)
    return [line for line in out if line.strip()]


def strip_md(text: str) -> str:
    text = re.sub(r"^\s*(?:\d+\.\s+|#{2,6}\s+)", "", text)
    text = re.sub(r"^\s*-\s+", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = text.replace("**", "").replace("`", "")
    return text.strip()


def first_int(text: str, default: int = 0) -> int:
    match = re.search(r"\d+", text or "")
    return int(match.group(0)) if match else default


def load_report(batch_dir: Path) -> dict:
    path = batch_dir / "run-report.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def rel(path: Path) -> str:
    return path.relative_to(INBOX).as_posix()


def card_rows(lines: list[str]) -> str:
    rows = []
    for idx, line in enumerate(lines, 1):
        clean = strip_md(line.lstrip("- ").strip())
        if not clean:
            continue
        rows.append(
            f'<div class="article-item"><span class="article-index">{idx}</span>'
            f"<div><strong>{html.escape(clean.split('：', 1)[0][:44])}</strong>"
            f"<span>{html.escape(clean)}</span></div><span class=\"tag\">来源</span></div>"
        )
    return "\n".join(rows)


def build() -> None:
    batch_dir = latest_batch_dir()
    label = batch_dir.name
    md_path = batch_dir / f"000-{label}.md"
    html_path = batch_dir / f"000-{label}.html"
    md = read_text(md_path)
    report = load_report(batch_dir)

    conclusion = section_lines(md, "## 今日结论", ("## ",))
    health = section_lines(md, "## 渠道概览", ("## ",))
    issues = section_lines(md, "## 未进入正文", ("## 今日精选",))
    if not issues:
        issues = section_lines(md, "## 待处理", ("## 今日精选",))
    if not issues:
        issues = section_lines(md, "## Issue Pool", ("## 今日精选",))
    official = section_lines(md, "### AI 官方与代码源", ("### Twitter / X 应用层", "## Podcast"))
    x_app = section_lines(md, "### Twitter / X 应用层", ("## Podcast", "## 关注"))
    media = section_lines(md, "## Podcast / YouTube / 抖音", ("## 关注",))

    totals = report.get("totals", {})
    health_report = report.get("health", {})
    raw = totals.get("items") or first_int(" ".join(conclusion))
    accepted = totals.get("kept") or 0
    filtered = totals.get("filtered") or 0
    needs_attention = health_report.get("needs_attention")
    if needs_attention is None:
        needs_attention = len([line for line in health if "⚠" in line])

    issue_rows = card_rows([line for line in issues if line.startswith("- ")])
    if not issue_rows:
        issue_rows = '<p class="empty">当前批次没有需要展示的问题。</p>'
    display_count = len(
        re.findall(r"(?m)^(?:\d+\. |#### |\s*-\s+\*\*\[)", md)
    )

    css = """
    :root{--paper:#f3f6f5;--ink:#14201f;--muted:#617170;--line:#cfdbd7;--panel:#fbfdfb;--green:#0f756a;--red:#b42318;--amber:#9a6200;--blue:#244e83;--radius:8px}
    *{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Noto Sans CJK SC",sans-serif;letter-spacing:0}
    .topbar{position:sticky;top:0;z-index:3;background:rgba(243,246,245,.96);border-bottom:1px solid var(--line);backdrop-filter:blur(14px)}
    .topbar-inner{width:min(1440px,calc(100% - 28px));margin:0 auto;padding:12px 0;display:grid;grid-template-columns:240px 1fr auto;gap:14px;align-items:center}
    .brand{display:flex;gap:10px;align-items:center}.mark{width:38px;height:38px;border-radius:8px;background:#173d38;color:#fff;display:grid;place-items:center;font-weight:800}.brand strong{display:block}.brand span{display:block;color:var(--muted);font-size:12px}
    .health-strip{display:grid;grid-template-columns:repeat(5,minmax(110px,1fr));gap:8px}.pill{border:1px solid var(--line);border-radius:8px;background:var(--panel);padding:8px 10px;display:flex;justify-content:space-between;gap:8px;font-size:13px}.pill b{color:var(--green)}.pill.warn b{color:var(--amber)}.pill.bad b{color:var(--red)}
    .layout{width:min(1440px,calc(100% - 28px));margin:18px auto;display:grid;grid-template-columns:280px 1fr 330px;gap:16px;align-items:start}
    aside,.card,.hero{background:var(--panel);border:1px solid var(--line);border-radius:8px}.rail,.issues{position:sticky;top:78px;padding:14px}.rail h2,.issues h2{margin:0 0 10px;font-size:16px}.rail a{display:block;padding:9px 10px;border-radius:7px;color:var(--ink);text-decoration:none}.rail a:hover{background:#e8efec}
    .hero{padding:22px;margin-bottom:14px}.hero h1{margin:0 0 8px;font-size:26px}.hero p{margin:0;color:var(--muted);line-height:1.65}.metric-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:16px}.metric{background:#eef5f2;border:1px solid var(--line);border-radius:8px;padding:12px}.metric strong{display:block;font-size:24px;color:var(--green)}.metric span{color:var(--muted);font-size:12px}
    .card{padding:18px;margin-bottom:14px}.card h2{margin:0 0 10px;font-size:20px}.card h3{margin:4px 0 10px;font-size:17px}.card ul{margin:0;padding-left:18px;line-height:1.8}.empty{color:var(--muted)}
    .article-list{display:grid;gap:10px}.article-item{display:grid;grid-template-columns:34px 1fr auto;gap:10px;align-items:start;border-top:1px solid var(--line);padding-top:10px}.article-index{height:28px;border-radius:7px;background:#deeeea;color:#0f756a;display:grid;place-items:center;font-weight:700}.article-item strong{display:block;margin-bottom:4px}.article-item span:not(.article-index):not(.tag){color:var(--muted);line-height:1.55}.tag{font-size:12px;color:#0f756a;border:1px solid #a8d8d1;border-radius:999px;padding:3px 8px;white-space:nowrap}
    .digest-frame{width:100%;height:76vh;border:1px solid var(--line);border-radius:8px;background:white}.issue{border-left:3px solid var(--amber);padding:10px 0 10px 10px;border-top:1px solid var(--line)}.issue:first-of-type{border-top:0}.issue strong{display:block;font-size:14px}.issue p{margin:5px 0 0;color:var(--muted);font-size:13px;line-height:1.55}
    @media(max-width:1100px){.layout{grid-template-columns:1fr}.rail,.issues{position:static}.topbar-inner{grid-template-columns:1fr}.health-strip{grid-template-columns:1fr 1fr}.metric-grid{grid-template-columns:1fr 1fr}}
    """

    issue_count = len([line for line in issues if line.startswith("- ")])
    health_html = "".join(f"<li>{html.escape(strip_md(line.lstrip('- ')))}</li>" for line in health)
    conclusion_html = "".join(f"<li>{html.escape(strip_md(line.lstrip('- ')))}</li>" for line in conclusion)

    doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Park-IO Inbox Console · {label}</title>
  <style>{css}</style>
</head>
<body>
  <header class="topbar">
    <div class="topbar-inner">
      <div class="brand"><div class="mark">PIO</div><div><strong>Park-IO Inbox Console</strong><span>由 {html.escape(md_path.name)} 生成</span></div></div>
      <div class="health-strip">
        <div class="pill"><span>健康渠道</span><b>{health_report.get('healthy', '-')}</b></div>
        <div class="pill"><span>今日新增</span><b>{health_report.get('new_today', '-')}</b></div>
        <div class="pill warn"><span>需关注</span><b>{needs_attention}</b></div>
        <div class="pill"><span>获取池</span><b>{raw}</b></div>
        <div class="pill"><span>展示</span><b>{display_count}</b></div>
      </div>
      <a class="tag" href="{html.escape(rel(html_path))}">打开日报 HTML</a>
    </div>
  </header>
  <main class="layout">
    <aside class="rail">
      <h2>视图</h2>
      <a href="#overview">今日总览</a>
      <a href="#issues">未进入正文</a>
      <a href="#digest">日报正文</a>
      <a href="#raw">原始口径</a>
    </aside>
    <section>
      <section class="hero" id="overview">
        <h1>{label} Daily Inbox</h1>
        <p>Console 不再维护独立日报文案；统计、问题和正文都来自当前批次的 Markdown / run-report。若日报里有转录未完成、低信息、feed 冻结，这里同步显示。</p>
        <div class="metric-grid">
          <div class="metric"><strong>{raw}</strong><span>获取池</span></div>
          <div class="metric"><strong>{accepted}</strong><span>Accepted Pool</span></div>
          <div class="metric"><strong>{filtered}</strong><span>Filtered Pool</span></div>
          <div class="metric"><strong>{issue_count}</strong><span>未进入正文</span></div>
        </div>
      </section>
      <section class="card">
        <h2>渠道概览</h2>
        <ul>{health_html}</ul>
      </section>
      <section class="card">
        <h2>今日结论</h2>
        <ul>{conclusion_html}</ul>
      </section>
      <section class="card" id="issues">
        <h2>未进入正文</h2>
        <div class="article-list">{issue_rows}</div>
      </section>
      <section class="card" id="digest">
        <h2>日报正文</h2>
        <iframe class="digest-frame" src="{html.escape(rel(html_path))}" title="Daily newsletter"></iframe>
      </section>
      <section class="card" id="raw">
        <h2>内容路径摘录</h2>
        <h3>AI 官方与代码源</h3>
        <div class="article-list">{card_rows([l for l in official if l.startswith(('1. ', '- **'))][:8])}</div>
        <h3>Twitter / X 应用层</h3>
        <div class="article-list">{card_rows([l for l in x_app if l.startswith('- **[')][:8])}</div>
        <h3>Podcast / YouTube / 抖音</h3>
        <div class="article-list">{card_rows([l for l in media if l.startswith(('#### ', '- '))][:8])}</div>
      </section>
    </section>
    <aside class="issues">
      <h2>维护提示</h2>
      <div class="issue"><strong>单一事实源</strong><p>Markdown 是内容事实源；HTML/PNG/Console 只渲染或引用它，不再单独写日报判断。</p></div>
      <div class="issue"><strong>当前问题</strong><p>{html.escape('; '.join(strip_md(l.lstrip('- ')) for l in issues if l.startswith('- ')) or '无')}</p></div>
    </aside>
  </main>
</body>
</html>
"""
    OUT.write_text(doc, encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    build()
