#!/usr/bin/env python3
"""Generate the owner-facing Daily Inbox dashboard."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from html import escape
from pathlib import Path

from lib import PARKIO, ROOT, load_sources, parse_frontmatter, today
import summarize

PUSH_RE = re.compile(r"<!-- parkio-push-items:(.*?) -->", re.S)
WECHAT_URL_RE = re.compile(r"https://mp\.weixin\.qq\.com/s/[A-Za-z0-9_-]+")


def latest_line(path: Path, needle: str) -> str:
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in reversed(lines):
        if needle in line:
            return line
    return ""


def next_wall_clock(hour: int) -> datetime:
    now = datetime.now()
    candidate = now.replace(hour=hour, minute=30 if hour == 8 else 0, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def next_push_text() -> str:
    return next_wall_clock(8).strftime("%Y-%m-%d %H:%M")


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def check_command(cmd: list[str], timeout: int = 8) -> tuple[bool, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception as exc:
        return False, f"{type(exc).__name__}: {str(exc)[:120]}"
    text = (result.stdout or result.stderr or "").strip().splitlines()
    detail = text[-1] if text else f"exit={result.returncode}"
    return result.returncode == 0, detail[:180]


def dependency_checks() -> list[dict]:
    twitter_auth = ROOT / "twitter-auth.env"
    checks = [
        {
            "name": "Python 运行时",
            "status": "ok" if sys.version_info >= (3, 11) else "failed",
            "detail": f"{sys.executable} {sys.version.split()[0]}",
        },
        {
            "name": "X 登录态",
            "status": "ok" if twitter_auth.exists() else "failed",
            "detail": "twitter-auth.env 可用" if twitter_auth.exists() else "twitter-auth.env 缺失",
        }
    ]
    ok, detail = check_command([sys.executable, "-c", "import mlx_whisper; print('mlx_whisper ok')"])
    checks.append({"name": "MLX Whisper", "status": "ok" if ok else "failed", "detail": detail})
    ok, detail = check_command(["/usr/bin/curl", "-fsS", "http://localhost:4000/feeds/MP_WXS_3223096120.json"])
    checks.append({"name": "WeWe RSS", "status": "ok" if ok else "failed", "detail": "localhost:4000 可访问" if ok else detail})
    ok, detail = check_command(
        [
            sys.executable,
            "-c",
            "import sys; from pathlib import Path; sys.path.insert(0, str(Path.home()/'content-toolkit/capabilities/download')); from content_downloader.adapters.douyin.adapter import DouyinAdapter; from content_downloader.adapters.douyin.api_client import DouyinAPIClient; print('douyin downloader api client ok')",
        ]
    )
    checks.append({"name": "抖音下载器", "status": "ok" if ok else "failed", "detail": detail})
    cookie = PARKIO / "secrets" / "content-ops" / "douyin-cookies.json"
    checks.append({"name": "抖音 Cookie", "status": "ok" if cookie.exists() else "failed", "detail": "cookie 文件存在" if cookie.exists() else "cookie 文件缺失"})
    return checks


def status_label(status: str) -> str:
    return {
        "ok_new": "有新增",
        "ok_no_new": "成功无新增",
        "filtered_out": "抓到但过滤",
        "failed": "抓取失败",
        "not_configured": "未配置",
        "unsupported": "暂不支持",
    }.get(status, status or "未知")


def status_bucket(row: dict) -> str:
    status = row.get("status")
    if status == "ok_new":
        return "今日有新增"
    if status == "ok_no_new":
        return "成功但无新增"
    if status == "filtered_out":
        return "抓到但被过滤"
    if status == "failed":
        return "抓取失败"
    return "其他状态"


def manual_links_summary() -> dict:
    state = load_json(ROOT / "state.json").get("manual-links", {})
    manual_file = PARKIO / "inbox" / "manual-links.md"
    pending = 0
    if manual_file.exists():
        text = manual_file.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"^## Pending\s*$", text, flags=re.M)
        if match:
            start = match.end()
            next_match = re.search(r"^## .+$", text[start:], flags=re.M)
            section = text[start : start + next_match.start()] if next_match else text[start:]
            pending = len(WECHAT_URL_RE.findall(section))
    return {
        "pending": pending,
        "imported_total": len(state.get("seen_urls", [])),
        "imported_last_run": state.get("imported", 0),
        "failed_total": len(state.get("failed_records", [])),
        "last_fetch": state.get("last_fetch", ""),
    }


def media_queue_summary() -> tuple[dict[str, int], str]:
    queue = load_json(ROOT / "media-queue.json")
    counts: Counter[str] = Counter()
    for record in queue.values():
        counts[str(record.get("status") or "unknown")] += 1
    text = "；".join(f"{status}: {count}" for status, count in sorted(counts.items())) or "暂无音视频队列"
    return dict(counts), text


def channel_for_url(url: str) -> str:
    value = url.lower()
    if "x.com/" in value or "twitter.com/" in value:
        return "X"
    if "youtube.com/" in value or "youtu.be/" in value:
        return "YouTube"
    if "douyin.com/" in value:
        return "抖音"
    if "mp.weixin.qq.com/" in value:
        return "公众号"
    if "github.com/" in value:
        return "GitHub"
    if "anthropic.com/" in value or "openai.com/" in value or "claude.com/" in value:
        return "官方网页"
    return "网页"


def title_from_article(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("# "):
                return line.removeprefix("# ").strip()
    except OSError:
        return ""
    return ""


def item_frontmatter(path: Path) -> tuple[dict, str]:
    try:
        return parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return {}, ""


def pushed_urls_by_day() -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    sent_dir = PARKIO / "inbox" / "sent"
    for path in sorted(sent_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        match = PUSH_RE.search(text)
        urls: set[str] = set()
        if match:
            try:
                urls = {str(url) for url in json.loads(match.group(1)) if str(url).strip()}
            except json.JSONDecodeError:
                urls = set()
        out[path.stem] = urls
    return out


def sent_digest_summary(day: str) -> dict:
    short_day = day[2:]
    path = PARKIO / "inbox" / "sent" / f"{short_day}.md"
    if not path.exists():
        return {"path": path, "exists": False, "pushed": 0, "sections": []}
    text = path.read_text(encoding="utf-8", errors="replace")
    match = PUSH_RE.search(text)
    pushed = []
    if match:
        try:
            pushed = [str(url) for url in json.loads(match.group(1)) if str(url).strip()]
        except json.JSONDecodeError:
            pushed = []
    sections = []
    for line in text.splitlines():
        if line.startswith("### "):
            title = line.removeprefix("### ").strip()
            if title not in sections:
                sections.append(title)
    return {"path": path, "exists": True, "pushed": len(pushed), "sections": sections[:10]}


def library_profile_stats() -> list[dict]:
    pushed = set().union(*pushed_urls_by_day().values()) if pushed_urls_by_day() else set()
    root = PARKIO / "library" / "profiles"
    rows = []
    if not root.exists():
        return rows
    for profile in sorted(p for p in root.iterdir() if p.is_dir()):
        article_paths = sorted((profile / "items").glob("*/article.md"))
        channel_counts: Counter[str] = Counter()
        selected = 0
        latest_mtime = 0.0
        latest_title = ""
        for article in article_paths:
            fm, _body = item_frontmatter(article)
            url = str(fm.get("url", ""))
            channel_counts[channel_for_url(url)] += 1
            if url and url in pushed:
                selected += 1
            mtime = article.stat().st_mtime
            if mtime > latest_mtime:
                latest_mtime = mtime
                latest_title = title_from_article(article)
        total = len(article_paths)
        rows.append(
            {
                "profile": profile.name,
                "total": total,
                "selected": selected,
                "rate": (selected / total * 100) if total else 0,
                "channels": dict(channel_counts),
                "latest": latest_title,
                "latest_time": datetime.fromtimestamp(latest_mtime).strftime("%Y-%m-%d") if latest_mtime else "-",
            }
        )
    return rows


def independent_link_count() -> int:
    return len(list((PARKIO / "library" / "独立链接").glob("*/article.md")))


def today_funnel(sources_today: list) -> dict:
    total = sum(len(src["items"]) for src in sources_today)
    kept = sum(len(src["kept"]) for src in sources_today)
    filtered = sum(len(src["filtered"]) for src in sources_today)
    by_source = []
    for src in sources_today:
        name = src["fm"].get("profile_name") or src["fm"].get("source_name") or src["file"].stem
        by_source.append(
            {
                "name": name,
                "file": src["file"].name,
                "total": len(src["items"]),
                "kept": len(src["kept"]),
                "filtered": len(src["filtered"]),
            }
        )
    by_source.sort(key=lambda row: (-row["total"], row["name"]))
    return {"total": total, "kept": kept, "filtered": filtered, "by_source": by_source}


def new_bucket(title: str, logo: str, note: str, sub_labels: list[tuple[str, str]]) -> dict:
    return {
        "title": title,
        "logo": logo,
        "note": note,
        "source_count": 0,
        "failed": 0,
        "raw": 0,
        "kept": 0,
        "filtered": 0,
        "subs": {
            key: {"label": label, "logo": logo, "source_count": 0, "failed": 0, "raw": 0, "kept": 0, "filtered": 0}
            for key, label, logo in sub_labels
        },
    }


def empty_intake_buckets() -> dict[str, dict]:
    return {
        "official": new_bucket(
            "厂商动态",
            "AI",
            "OpenAI 与 Anthropic 相关官方渠道和关键个人账号。",
            [("openai", "OpenAI / ChatGPT / Codex", "OAI"), ("anthropic", "Anthropic / Claude", "ANT")],
        ),
        "tracked": new_bucket(
            "实时监控渠道",
            "RT",
            "你长期关注的 X、视频、播客、抖音、公众号等来源。",
            [("x", "X", "X"), ("media", "YouTube / Podcast", "YT"), ("douyin", "抖音", "抖"), ("wechat", "公众号", "微"), ("other", "其他", "其")],
        ),
        "manual": new_bucket(
            "手动添加",
            "+",
            "你主动收藏、点赞或贴到 manual-links 的内容；默认进入正文或资料库。",
            [("manual_link", "手动链接", "+"), ("x_saved", "X 收藏", "X"), ("other", "其他手动内容", "其")],
        ),
    }


def official_sub_from_text(text: str) -> str | None:
    value = text.lower()
    if any(token in value for token in ["openai", "chatgpt", "codex", "sam altman", "greg brockman", "kevin weil", "mark chen"]):
        return "openai"
    if any(token in value for token in ["anthropic", "claude", "dario amodei", "daniela amodei", "mike krieger"]):
        return "anthropic"
    return None


def classify_health_row(row: dict) -> tuple[str, str]:
    name = str(row.get("name") or "")
    platform = str(row.get("platform") or "").lower()
    official = official_sub_from_text(name)
    if official:
        return "official", official
    if platform == "twitter":
        return "tracked", "x"
    if platform == "douyin":
        return "tracked", "douyin"
    if platform == "wechat":
        return "tracked", "wechat"
    if platform == "rss" and any(token in name.lower() for token in ["youtube", "podcast", "dwarkesh", "latent space", "no priors", "y combinator", "powerfuljre"]):
        return "tracked", "media"
    return "tracked", "other"


def classify_today_source(src: dict) -> tuple[str, str]:
    fm = src["fm"]
    text = " ".join(str(fm.get(key) or "") for key in ["profile_id", "profile_name", "source_name", "category", "channel", "platform", "url"])
    value = text.lower()
    if "x-saved" in value or "personal-saved" in value or "我的 x 收藏" in text:
        return "manual", "x_saved"
    if "manual-link" in value or "wechat-manual" in value:
        return "manual", "manual_link"
    official = official_sub_from_text(text)
    if official:
        return "official", official
    if any(token in value for token in ["video-podcast", "youtube", "podcast"]):
        return "tracked", "media"
    if "douyin" in value or "抖音" in text:
        return "tracked", "douyin"
    if "wechat" in value or "公众号" in text:
        return "tracked", "wechat"
    if any(token in value for token in ["twitter", " x", "ai-personal", "自媒体", " ai"]):
        return "tracked", "x"
    return "tracked", "other"


def add_intake_counts(target: dict, raw: int = 0, kept: int = 0, filtered: int = 0, source_count: int = 0, failed: int = 0) -> None:
    target["raw"] += raw
    target["kept"] += kept
    target["filtered"] += filtered
    target["source_count"] += source_count
    target["failed"] += failed


def build_intake_buckets(sources_today: list, health: list[dict]) -> list[dict]:
    buckets = empty_intake_buckets()
    for row in health:
        bucket_key, sub_key = classify_health_row(row)
        bucket = buckets[bucket_key]
        sub = bucket["subs"][sub_key]
        failed = 1 if row.get("status") == "failed" else 0
        add_intake_counts(bucket, source_count=1, failed=failed)
        add_intake_counts(sub, source_count=1, failed=failed)
    for src in sources_today:
        bucket_key, sub_key = classify_today_source(src)
        bucket = buckets[bucket_key]
        sub = bucket["subs"][sub_key]
        raw = len(src["items"])
        kept = len(src["kept"])
        filtered = len(src["filtered"])
        add_intake_counts(bucket, raw=raw, kept=kept, filtered=filtered)
        add_intake_counts(sub, raw=raw, kept=kept, filtered=filtered)
    return [buckets["official"], buckets["tracked"], buckets["manual"]]


def render_logo(value: str, class_name: str = "logo") -> str:
    return f"<span class='{class_name}'>{escape(value)}</span>"


def render_intake_funnel(buckets: list[dict], pushed: int) -> str:
    max_raw = max([bucket["raw"] for bucket in buckets] + [1])
    rows = []
    for idx, bucket in enumerate(buckets):
        width = 58 + (bucket["raw"] / max_raw * 34 if max_raw else 0)
        if bucket["raw"] == 0:
            width = 54
        subs = []
        for sub in bucket["subs"].values():
            if not (sub["source_count"] or sub["raw"] or sub["failed"]):
                continue
            subs.append(
                "<div class='sub-source'>"
                f"{render_logo(sub['logo'], 'mini-logo')}"
                f"<span>{escape(sub['label'])}</span>"
                f"<strong>{sub['raw']}</strong>"
                f"<em>入选 {sub['kept']} · 过滤 {sub['filtered']} · 来源 {sub['source_count']}</em>"
                "</div>"
            )
        if not subs:
            subs.append("<div class='sub-source empty'><span>今天无新增</span><strong>0</strong><em>来源正常时无需处理</em></div>")
        rows.append(
            "<div class='intake-row'>"
            "<div class='intake-title'>"
            f"{render_logo(bucket['logo'])}"
            f"<div><strong>{escape(bucket['title'])}</strong><span>{escape(bucket['note'])}</span></div>"
            "</div>"
            f"<div class='funnel-slice slice-{idx}' style='width:{width:.1f}%'>"
            f"<div><strong>{bucket['raw']}</strong><span>今日抓到</span></div>"
            f"<div><strong>{bucket['kept']}</strong><span>进入正文</span></div>"
            f"<div><strong>{bucket['filtered']}</strong><span>被过滤</span></div>"
            f"<div><strong>{bucket['failed']}</strong><span>失败来源</span></div>"
            "</div>"
            f"<div class='sub-grid'>{''.join(subs)}</div>"
            "</div>"
        )
    return f"""
      <section class="panel intake-panel">
        <div class="section-head">
          <div>
            <h2>今日入口漏斗</h2>
            <p>默认只看今天：三大入口先汇总，再拆到具体渠道。数字回答的是“从哪里来、留下多少、哪里坏了”。</p>
          </div>
          <div class="output-badge"><strong>{pushed}</strong><span>今日推送链接</span></div>
        </div>
        <div class="intake-funnel">{''.join(rows)}</div>
      </section>
    """


def render_metric(title: str, value: object, note: str = "") -> str:
    return f"<div class='metric-card'><div class='metric-value'>{escape(str(value))}</div><div class='metric-title'>{escape(title)}</div><p>{escape(note)}</p></div>"


def render_rows(rows: list[str]) -> str:
    return "\n".join(rows) if rows else "<tr><td colspan='5' class='muted'>暂无数据</td></tr>"


def pct(value: int, total: int) -> str:
    if total <= 0:
        return "0%"
    return f"{value / total * 100:.0f}%"


def conic_gradient(parts: list[tuple[str, int, str]], total: int) -> str:
    if total <= 0:
        return "conic-gradient(#d9ded7 0deg 360deg)"
    start = 0.0
    segments = []
    for _label, value, color in parts:
        if value <= 0:
            continue
        end = start + (value / total) * 360
        segments.append(f"{color} {start:.1f}deg {end:.1f}deg")
        start = end
    if start < 360:
        segments.append(f"#e5e9e3 {start:.1f}deg 360deg")
    return "conic-gradient(" + ", ".join(segments) + ")"


def render_donut(title: str, parts: list[tuple[str, int, str]], total: int, center_note: str) -> str:
    legend = "".join(
        f"<div class='legend-row'><span class='dot' style='background:{escape(color)}'></span><span>{escape(label)}</span><strong>{value}</strong></div>"
        for label, value, color in parts
    )
    return f"""
      <div class="viz-card">
        <h3>{escape(title)}</h3>
        <div class="donut-wrap">
          <div class="donut" style="background:{conic_gradient(parts, total)}"><div><strong>{total}</strong><span>{escape(center_note)}</span></div></div>
          <div class="legend">{legend}</div>
        </div>
      </div>
    """


def render_funnel(total: int, kept: int, filtered: int, pushed: int) -> str:
    stages = [
        ("抓到原始内容", total, "#1d4f45"),
        ("进入正文", kept, "#0f766e"),
        ("推送链接", pushed, "#2563eb"),
        ("被过滤", filtered, "#b45309"),
    ]
    max_value = max([value for _label, value, _color in stages] + [1])
    rows = []
    for label, value, color in stages:
        width = max(8, value / max_value * 100)
        rows.append(
            f"<div class='funnel-row'><div class='funnel-label'>{escape(label)}</div><div class='funnel-track'><div class='funnel-bar' style='width:{width:.1f}%;background:{color}'></div></div><div class='funnel-num'>{value}</div></div>"
        )
    return f"""
      <div class="viz-card wide">
        <h3>今日处理漏斗</h3>
        <p>先看总量，再看进入正文和最终推送。过滤不是错误，只说明它没有进入今日正文。</p>
        <div class="funnel">{''.join(rows)}</div>
      </div>
    """


def render_workflow_diagram() -> str:
    steps = [
        ("收集原始内容", "抓取脚本", "RSS / X / 公众号 / 视频 / 手动链接"),
        ("进入待处理区", "待处理文件", "按 Profile + 日期进入待处理队列"),
        ("生成简报", "评分与合并", "打分、合并、生成中文正文"),
        ("质量门检查", "硬规则 + AI 质检", "拦截旁白、内部元数据、重复标题"),
        ("推送与归档", "Telegram + 资料库", "推送给读者，沉淀到资料库"),
    ]
    nodes = []
    for idx, (title, code, desc) in enumerate(steps):
        arrow = "<div class='flow-arrow'>→</div>" if idx < len(steps) - 1 else ""
        nodes.append(
            f"<div class='flow-node'><strong>{escape(title)}</strong><span>{escape(code)}</span><p>{escape(desc)}</p></div>{arrow}"
        )
    return f"<div class='workflow'>{''.join(nodes)}</div>"


def render_bar_chart(title: str, rows: list[tuple[str, int]], note: str) -> str:
    max_value = max([value for _label, value in rows] + [1])
    bars = []
    for label, value in rows:
        width = max(4, value / max_value * 100)
        bars.append(
            f"<div class='bar-row'><span>{escape(label)}</span><div class='bar-track'><div class='bar' style='width:{width:.1f}%'></div></div><strong>{value}</strong></div>"
        )
    return f"""
      <div class="viz-card">
        <h3>{escape(title)}</h3>
        <p>{escape(note)}</p>
        <div class="bars">{''.join(bars) if bars else '<p class="muted">暂无数据</p>'}</div>
      </div>
    """


def render_top_profiles_chart(profile_stats: list[dict]) -> str:
    rows = [(row["profile"], row["total"]) for row in sorted(profile_stats, key=lambda value: (-value["total"], value["profile"]))[:10]]
    return render_bar_chart("资料库重点 Profile", rows, "按累计沉淀内容排序，帮助判断哪些来源已经形成长期资产。")


def render_channel_chart(profile_stats: list[dict], independent_total: int) -> str:
    counts: Counter[str] = Counter()
    for row in profile_stats:
        counts.update(row["channels"])
    if independent_total:
        counts["独立链接"] += independent_total
    preferred = ["X", "公众号", "YouTube", "GitHub", "官方网页", "抖音", "独立链接", "网页"]
    rows = [(name, counts[name]) for name in preferred if counts.get(name)]
    rows.extend((name, value) for name, value in counts.most_common() if name not in preferred)
    return render_bar_chart("长期资产渠道构成", rows[:10], "看资料库主要由哪些渠道构成，避免误以为每日简报只是一堆 X。")


def render() -> str:
    date = today()
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    scores = summarize.load_scores()
    sources_today, _ = summarize.read_today_items(date, scores)
    health = summarize.source_health(sources_today, date)
    configured = load_sources()
    funnel = today_funnel(sources_today)
    sent = sent_digest_summary(date)
    pushed_count = sent["pushed"] if sent["exists"] else 0
    manual = manual_links_summary()
    media_counts, media_text = media_queue_summary()
    profile_stats = library_profile_stats()
    profile_total = sum(row["total"] for row in profile_stats)
    selected_total = sum(row["selected"] for row in profile_stats)
    independent_total = independent_link_count()
    failed = [row for row in health if row["status"] == "failed"]
    intake_buckets = build_intake_buckets(sources_today, health)

    fetch_done = latest_line(ROOT / "logs" / "fetch-all.log", "fetch-all DONE")
    push_done = latest_line(ROOT / "logs" / "push-digest.log", "push-digest DONE")
    quality_line = latest_line(ROOT / "logs" / "push-digest.log", "quality-check.py")

    buckets: dict[str, list[dict]] = defaultdict(list)
    for row in health:
        buckets[status_bucket(row)].append(row)
    health_counts = Counter(row["status"] for row in health)
    health_parts = [
        ("有新增", health_counts.get("ok_new", 0), "#0f766e"),
        ("成功无新增", health_counts.get("ok_no_new", 0), "#8fb8aa"),
        ("抓到但过滤", health_counts.get("filtered_out", 0), "#b45309"),
        ("失败", health_counts.get("failed", 0), "#b42318"),
        ("其他", sum(v for k, v in health_counts.items() if k not in {"ok_new", "ok_no_new", "filtered_out", "failed"}), "#7c8790"),
    ]
    today_parts = [
        ("进入正文", funnel["kept"], "#0f766e"),
        ("过滤", funnel["filtered"], "#b45309"),
    ]
    bucket_cards = "".join(
        render_metric(name, len(items), "、".join(row["name"] for row in items[:6]) + ("…" if len(items) > 6 else ""))
        for name, items in buckets.items()
    )

    source_rows = []
    for row in funnel["by_source"][:40]:
        source_rows.append(
            f"<tr><td>{escape(row['name'])}</td><td>{escape(row['file'])}</td><td>{row['total']}</td><td>{row['kept']}</td><td>{row['filtered']}</td></tr>"
        )

    health_rows = []
    for row in health:
        health_rows.append(
            f"<tr><td>{escape(row['name'])}</td><td>{escape(row['platform'])}</td><td><span class='status {escape(row['status'])}'>{escape(status_label(row['status']))}</span></td><td>{escape(row['detail'])}</td></tr>"
        )

    dependency_rows = []
    for row in dependency_checks():
        dependency_rows.append(
            f"<tr><td>{escape(row['name'])}</td><td><span class='status {escape(row['status'])}'>{'正常' if row['status'] == 'ok' else '异常'}</span></td><td>{escape(row['detail'])}</td></tr>"
        )

    profile_rows = []
    for row in sorted(profile_stats, key=lambda value: (-value["total"], value["profile"]))[:50]:
        channels = " / ".join(f"{k} {v}" for k, v in sorted(row["channels"].items()))
        profile_rows.append(
            f"<tr><td>{escape(row['profile'])}</td><td>{row['total']}</td><td>{row['selected']}</td><td>{row['rate']:.0f}%</td><td>{escape(channels)}</td><td>{escape(row['latest_time'])}</td><td>{escape(row['latest'][:80])}</td></tr>"
        )

    sections = "、".join(sent["sections"]) if sent["sections"] else "尚未生成今日推送"
    today_verdict = "今日推送已完成" if sent["exists"] else "今日尚未推送"
    if failed:
        today_verdict += f"；{len(failed)} 个来源需要维护"
    elif funnel["total"] == 0:
        today_verdict += "；暂无新增 raw input"
    else:
        today_verdict += "；来源健康无阻塞"
    page = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Daily Inbox 内部状态面板</title>
  <style>
    :root {{
      --bg: #f4f5f2;
      --panel: #fffffb;
      --ink: #17201b;
      --muted: #637069;
      --line: #d9ded7;
      --good: #0f766e;
      --warn: #9a5b00;
      --bad: #b42318;
      --accent: #1d4f45;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--bg); color: var(--ink); font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif; }}
    main {{ width: min(1180px, calc(100% - 28px)); margin: 0 auto; padding: 28px 0 52px; }}
    header {{ border-bottom: 1px solid var(--line); padding: 8px 0 22px; margin-bottom: 18px; }}
    h1 {{ margin: 0; font-size: 28px; letter-spacing: 0; }}
    h2 {{ margin: 26px 0 12px; font-size: 18px; }}
    h3 {{ margin: 0 0 8px; font-size: 15px; }}
    p {{ margin: 6px 0 0; color: var(--muted); line-height: 1.55; }}
    .muted {{ color: var(--muted); }}
    .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }}
    .two {{ grid-template-columns: 1.1fr .9fr; }}
    .metric-card, .panel, .viz-card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; box-shadow: 0 1px 0 rgba(23,32,27,.03); }}
    .hero {{ display: grid; grid-template-columns: 1.25fr .75fr; gap: 12px; align-items: stretch; margin-bottom: 14px; }}
    .hero-summary {{ background: #123c35; color: #f5fbf8; border-radius: 8px; padding: 22px; }}
    .hero-summary h2 {{ margin: 0 0 10px; color: #fff; font-size: 24px; }}
    .hero-summary p {{ color: #cfe0db; max-width: 760px; }}
    .hero-summary .pill {{ color: #e6fffa; border-color: rgba(230,255,250,.25); background: rgba(255,255,255,.08); }}
    .metric-value {{ color: var(--accent); font-weight: 800; font-size: 30px; line-height: 1; }}
    .metric-title {{ margin-top: 8px; font-weight: 700; }}
    .section-head {{ display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; margin-bottom: 14px; }}
    .section-head h2 {{ margin: 0 0 4px; }}
    .output-badge {{ min-width: 132px; border: 1px solid rgba(15,118,110,.2); background: #edf8f5; color: var(--accent); border-radius: 8px; padding: 12px; text-align: right; }}
    .output-badge strong {{ display: block; font-size: 28px; line-height: 1; }}
    .output-badge span {{ display: block; color: #4e655e; font-size: 12px; margin-top: 4px; }}
    .intake-panel {{ margin-top: 14px; }}
    .intake-funnel {{ display: grid; gap: 14px; }}
    .intake-row {{ display: grid; grid-template-columns: 260px 1fr 1.25fr; gap: 14px; align-items: center; padding: 12px 0; border-top: 1px solid #edf0eb; }}
    .intake-row:first-child {{ border-top: 0; padding-top: 0; }}
    .intake-title {{ display: grid; grid-template-columns: 42px 1fr; gap: 10px; align-items: center; }}
    .intake-title strong {{ display: block; font-size: 16px; }}
    .intake-title span {{ display: block; color: var(--muted); font-size: 12px; line-height: 1.45; margin-top: 3px; }}
    .logo, .mini-logo {{ display: inline-grid; place-items: center; border-radius: 10px; font-weight: 800; letter-spacing: 0; }}
    .logo {{ width: 42px; height: 42px; background: #103d36; color: #f6fffb; font-size: 13px; box-shadow: inset 0 0 0 1px rgba(255,255,255,.12); }}
    .intake-title .logo {{ color: #f6fffb; font-size: 13px; line-height: 1; margin-top: 0; }}
    .mini-logo {{ width: 28px; height: 28px; border-radius: 8px; color: #0b4239; background: #e6f4ef; font-size: 11px; }}
    .funnel-slice {{ margin: 0 auto; min-width: 290px; color: #fff; display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; padding: 16px 34px; clip-path: polygon(4% 0, 96% 0, 86% 100%, 14% 100%); }}
    .slice-0 {{ background: linear-gradient(90deg, #123c35, #0f766e); }}
    .slice-1 {{ background: linear-gradient(90deg, #1b4f72, #2878a8); }}
    .slice-2 {{ background: linear-gradient(90deg, #5b3d12, #b7791f); }}
    .funnel-slice div {{ text-align: center; }}
    .funnel-slice strong {{ display: block; font-size: 24px; line-height: 1; }}
    .funnel-slice span {{ display: block; font-size: 11px; opacity: .84; margin-top: 5px; white-space: nowrap; }}
    .sub-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }}
    .sub-source {{ min-height: 58px; display: grid; grid-template-columns: 28px 1fr auto; gap: 8px; align-items: center; background: #fafaf6; border: 1px solid #e0e5dd; border-radius: 8px; padding: 8px; }}
    .sub-source span {{ font-weight: 700; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .sub-source strong {{ color: var(--accent); font-size: 18px; }}
    .sub-source em {{ grid-column: 2 / 4; color: var(--muted); font-style: normal; font-size: 11px; margin-top: -5px; }}
    .sub-source.empty {{ grid-template-columns: 1fr auto; }}
    .visual-grid {{ display: grid; grid-template-columns: 1.2fr .8fr; gap: 12px; margin: 12px 0; }}
    .viz-card.wide {{ min-height: 100%; }}
    .donut-wrap {{ display: grid; grid-template-columns: 168px 1fr; gap: 16px; align-items: center; }}
    .donut {{ width: 156px; height: 156px; border-radius: 50%; display: grid; place-items: center; box-shadow: inset 0 0 0 1px rgba(23,32,27,.08); }}
    .donut > div {{ width: 92px; height: 92px; border-radius: 50%; background: var(--panel); display: grid; place-items: center; text-align: center; padding: 12px; }}
    .donut strong {{ display: block; font-size: 24px; line-height: 1; }}
    .donut span {{ display: block; color: var(--muted); font-size: 12px; margin-top: 4px; }}
    .legend {{ display: grid; gap: 8px; }}
    .legend-row {{ display: grid; grid-template-columns: 14px 1fr auto; gap: 8px; align-items: center; color: #46554e; font-size: 13px; }}
    .dot {{ width: 10px; height: 10px; border-radius: 50%; }}
    .funnel {{ display: grid; gap: 11px; margin-top: 14px; }}
    .funnel-row {{ display: grid; grid-template-columns: 86px 1fr 42px; gap: 10px; align-items: center; }}
    .funnel-label, .funnel-num {{ color: #46554e; font-size: 13px; }}
    .funnel-num {{ text-align: right; font-weight: 700; color: var(--ink); }}
    .funnel-track, .bar-track {{ background: #edf0eb; border-radius: 999px; overflow: hidden; height: 15px; }}
    .funnel-bar, .bar {{ height: 100%; border-radius: 999px; }}
    .workflow {{ display: grid; grid-template-columns: 1fr 26px 1fr 26px 1fr 26px 1fr 26px 1fr; gap: 6px; align-items: stretch; }}
    .flow-node {{ background: #fafaf6; border: 1px solid var(--line); border-radius: 8px; padding: 12px; }}
    .flow-node strong, .flow-node span {{ display: block; }}
    .flow-node span {{ color: var(--accent); font-size: 12px; margin-top: 2px; }}
    .flow-node p {{ font-size: 12px; }}
    .flow-arrow {{ display: grid; place-items: center; color: var(--muted); font-weight: 800; }}
    .bars {{ display: grid; gap: 9px; margin-top: 12px; }}
    .bar-row {{ display: grid; grid-template-columns: 112px 1fr 38px; gap: 10px; align-items: center; font-size: 13px; }}
    .bar-row span {{ color: #46554e; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .bar {{ background: linear-gradient(90deg, #0f766e, #42a391); }}
    details {{ margin-top: 14px; background: rgba(255,255,251,.55); border: 1px solid var(--line); border-radius: 8px; padding: 0 12px 12px; }}
    details[open] {{ background: transparent; border-color: transparent; padding: 0; }}
    summary {{ cursor: pointer; color: var(--accent); font-weight: 700; margin: 10px 0; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }}
    th, td {{ text-align: left; padding: 10px 11px; border-bottom: 1px solid #ecefeb; vertical-align: top; font-size: 13px; }}
    th {{ color: #46554e; background: #f7f8f4; font-weight: 700; }}
    tr:last-child td {{ border-bottom: 0; }}
    .status {{ display: inline-block; min-width: 72px; text-align: center; border-radius: 999px; padding: 2px 8px; border: 1px solid var(--line); white-space: nowrap; }}
    .ok, .ok_new, .ok_no_new {{ color: var(--good); border-color: #95d3c9; background: #edf8f5; }}
    .filtered_out, .not_configured, .unsupported {{ color: var(--warn); border-color: #efcd94; background: #fff8e8; }}
    .failed {{ color: var(--bad); border-color: #f0aaa3; background: #fff1ef; }}
    .pill-row {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }}
    .pill {{ border: 1px solid var(--line); border-radius: 999px; padding: 4px 9px; background: #fafaf6; color: #46554e; font-size: 12px; }}
    @media (max-width: 980px) {{ .hero, .visual-grid, .grid, .grid.two, .workflow, .intake-row {{ grid-template-columns: 1fr; }} .flow-arrow {{ display: none; }} main {{ width: min(100% - 20px, 1180px); }} .donut-wrap {{ grid-template-columns: 1fr; }} .funnel-slice {{ width: 100% !important; min-width: 0; }} .sub-grid {{ grid-template-columns: 1fr; }} .section-head {{ display: block; }} .output-badge {{ margin-top: 10px; text-align: left; }} }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Daily Inbox 内部状态面板</h1>
      <p>生成时间：{escape(generated)} · 日期：{escape(date)} · 这个页面面向维护者，用来检查抓取、筛选、推送和长期资料库。</p>
    </header>

    <section class="hero">
      <div class="hero-summary">
        <h2>{escape(today_verdict)}</h2>
        <p>今天系统抓到 {funnel['total']} 条内容，{funnel['kept']} 条进入正文，{funnel['filtered']} 条被过滤；Telegram 推送链接 {pushed_count} 条。先看三大入口漏斗，再展开表格排查细节。</p>
        <div class="pill-row">
          <span class="pill">下一次推送 {escape(next_push_text())}</span>
          <span class="pill">手动链接待导入 {manual['pending']}</span>
          <span class="pill">失败来源 {len(failed)}</span>
        </div>
      </div>
      {render_donut("今日内容去向", today_parts, max(funnel["total"], 0), "条原始内容")}
    </section>

    <section class="grid">
      {render_metric("活跃来源", len(configured), "来源清单中启用的来源")}
      {render_metric("今日待处理", funnel["total"], f"进入正文 {funnel['kept']} · 过滤 {funnel['filtered']}")}
      {render_metric("今日已推送", pushed_count, "Telegram 推送链接数")}
      {render_metric("失败来源", len(failed), "需要维护者查看来源健康")}
    </section>

    {render_intake_funnel(intake_buckets, pushed_count)}

    <h2>今日处理总览</h2>
    <section class="visual-grid">
      {render_funnel(funnel["total"], funnel["kept"], funnel["filtered"], pushed_count)}
      {render_donut("来源健康分布", health_parts, len(health), "个来源")}
    </section>

    <section class="panel">
      <h3>今日流程图</h3>
      {render_workflow_diagram()}
    </section>

    <section class="grid two" style="margin-top:12px">
      <div class="panel">
        <h3>今日最终输出</h3>
        <p><strong>推送文件：</strong>{escape(str(sent["path"])) if sent["exists"] else "今天尚未推送"}</p>
        <p><strong>正文区块：</strong>{escape(sections)}</p>
        <p><strong>下一次推送：</strong>{escape(next_push_text())}</p>
      </div>
      <div class="panel">
        <h3>最近运行日志</h3>
        <p><strong>最近 fetch：</strong>{escape(fetch_done or "unknown")}</p>
        <p><strong>最近 push：</strong>{escape(push_done or "unknown")}</p>
        <p><strong>质量门：</strong>{escape(quality_line or "push 前执行")}</p>
      </div>
    </section>

    <h2>手动收集入口</h2>
    <section class="grid">
      {render_metric("待导入链接", manual["pending"], "手动链接文件 / 待导入区")}
      {render_metric("累计导入", manual["imported_total"], f"上次导入 {manual['imported_last_run']} 条")}
      {render_metric("导入失败", manual["failed_total"], "失败链接会留在 Failed")}
      {render_metric("上次运行", manual["last_fetch"] or "-", "手动链接收集入口")}
    </section>

    <details>
      <summary>长期资料库总览</summary>
      <section class="grid">
        {render_metric("Profile 数", len(profile_stats), "长期资料库中的来源档案")}
        {render_metric("Profile 内容", profile_total, "已沉淀到来源档案的内容")}
        {render_metric("独立链接", independent_total, "未匹配到 Profile 的手动内容")}
        {render_metric("被选中次数", selected_total, "历史推送链接命中资料库内容")}
      </section>

      <section class="visual-grid">
        {render_top_profiles_chart(profile_stats)}
        {render_channel_chart(profile_stats, independent_total)}
      </section>
    </details>

    <details open>
      <summary>今日各来源处理结果</summary>
      <table>
        <thead><tr><th>来源/Profile</th><th>Raw 文件</th><th>抓到</th><th>进入正文</th><th>过滤</th></tr></thead>
        <tbody>{render_rows(source_rows)}</tbody>
      </table>
    </details>

    <details>
      <summary>资料库 Profile 统计</summary>
      <table>
        <thead><tr><th>Profile</th><th>累计内容</th><th>历史入选</th><th>入选率</th><th>渠道构成</th><th>最近更新</th><th>最近标题</th></tr></thead>
        <tbody>{render_rows(profile_rows)}</tbody>
      </table>
    </details>

    <details>
      <summary>来源健康明细</summary>
      <section class="grid" style="margin-bottom:12px">
        {bucket_cards}
      </section>
      <table>
        <thead><tr><th>来源</th><th>平台</th><th>状态</th><th>说明</th></tr></thead>
        <tbody>{render_rows(health_rows)}</tbody>
      </table>
    </details>

    <details>
      <summary>依赖检查</summary>
      <table>
        <thead><tr><th>依赖</th><th>状态</th><th>说明</th></tr></thead>
        <tbody>{render_rows(dependency_rows)}</tbody>
      </table>
    </details>

    <section class="panel" style="margin-top:18px">
      <h3>音视频处理队列</h3>
      <p>{escape(media_text)}</p>
      <div class="pill-row">
        {"".join(f"<span class='pill'>{escape(k)}: {v}</span>" for k, v in sorted(media_counts.items())) or "<span class='pill'>暂无记录</span>"}
      </div>
    </section>
  </main>
</body>
</html>
"""
    return page


def main() -> int:
    out = PARKIO / "inbox" / "status.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
