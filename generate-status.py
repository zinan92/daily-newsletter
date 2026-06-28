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

from lib import PARKIO, PROFILE_LIBRARY_DIR, ROOT, SENT_DIR, load_sources, parkio_secret_path, parse_frontmatter, today
import summarize
from run_report import build_run_report, latest_run_report, media_failures_for_date, write_run_report

PUSH_RE = re.compile(r"<!-- parkio-push-items:(.*?) -->", re.S)
WECHAT_URL_RE = re.compile(r"https://mp\.weixin\.qq\.com/s/[A-Za-z0-9_-]+")
WEWE_AUTH_ALERT = PARKIO / "_inbox" / "wewe-auth-alert.json"
MANUAL_PUSH_SCRIPT = ROOT / "manual-push.command"
BLOCKING_DEP_TOKENS = ("WeWe", "公众号", "YouTube")
LIVE_DASHBOARD_JSON = Path("/Users/wendy/work/park-ai-intel/public/source-health-live.json")


def latest_line(path: Path, needle: str) -> str:
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in reversed(lines):
        if needle in line:
            return line
    return ""


def write_live_dashboard_payload(payload: dict) -> None:
    try:
        LIVE_DASHBOARD_JSON.parent.mkdir(parents=True, exist_ok=True)
        LIVE_DASHBOARD_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError:
        return


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
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def load_wewe_auth_alert() -> dict:
    data = load_json(WEWE_AUTH_ALERT)
    return data if isinstance(data, dict) else {}


def wewe_auth_problem(data: dict | None = None) -> dict | None:
    data = data or load_wewe_auth_alert()
    status = data.get("status")
    if status == "invalid":
        names = "、".join(row.get("name", "未知账号") for row in data.get("invalid_accounts", [])[:4])
        return {
            "name": "WeWe 读书账号",
            "status": "failed",
            "detail": f"{names or '读书账号'} 已失效；需要扫码重新登录",
        }
    if status == "failed":
        return {
            "name": "WeWe 读书账号",
            "status": "failed",
            "detail": f"账号状态检测失败：{data.get('error', '未知错误')}",
        }
    return None


def render_wewe_auth_alert() -> str:
    data = load_wewe_auth_alert()
    problem = wewe_auth_problem(data)
    if not problem:
        return ""
    login = data.get("login", {}) if isinstance(data.get("login"), dict) else {}
    scan_url = login.get("scanUrl", "")
    qr_path = Path(str(login.get("qr_path") or ""))
    qr_html = ""
    if qr_path.exists():
        qr_html = "<img src='wewe-auth-qr.png' alt='WeWe RSS 登录二维码'>"
    elif scan_url:
        qr_html = f"<a class='auth-button' href='{escape(scan_url)}'>打开扫码链接</a>"
    account_rows = "".join(
        f"<li>{escape(str(row.get('name') or '未知账号'))}：{escape(str(row.get('status_label') or row.get('status') or '失效'))}</li>"
        for row in data.get("accounts", [])
    )
    checked_at = escape(str(data.get("checked_at") or "未知"))
    base_url = escape(str(data.get("base_url") or "http://localhost:4000"))
    return f"""
    <section class="auth-alert">
      <div class="auth-copy">
        <span class="alert-kicker">公众号登录态异常</span>
        <h2>WeWe RSS 读书账号失效，需要扫码恢复</h2>
        <p>检测时间：{checked_at}。恢复后，公众号 RSS 会按未见过的文章做 delta 回补，断更期间的新文章会进入下一次日报。</p>
        <ul>{account_rows or "<li>账号状态未知</li>"}</ul>
        <div class="pill-row">
          <a class="auth-button" href="{base_url}/dash/accounts">打开 WeWe 账号页</a>
          <span class="pill">二维码约 60 秒过期；若过期，等待下一次 fetch 自动刷新。</span>
        </div>
      </div>
      <div class="auth-qr">{qr_html}</div>
    </section>
    """


def check_command(cmd: list[str], timeout: int = 8) -> tuple[bool, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception as exc:
        return False, f"{type(exc).__name__}: {str(exc)[:120]}"
    text = (result.stdout or result.stderr or "").strip().splitlines()
    detail = text[-1] if text else f"exit={result.returncode}"
    return result.returncode == 0, detail[:180]


def dependency_checks() -> list[dict]:
    """Functional probes — reflect whether things actually WORK, not just whether a file
    exists. Source-backed deps (cookie/auth/bridge) are judged by recent real fetch
    outcomes via channel-health, so an expired cookie or frozen bridge shows red, not green."""
    twitter_auth = ROOT / "twitter-auth.env"
    cookie = parkio_secret_path("douyin-cookies.json")
    try:
        ch = summarize._channel_health_states()
    except Exception:
        ch = {}
    def by_platform(*plats):
        return [v for v in ch.values() if v.get("platform") in plats]

    checks = [{
        "name": "Python 运行时",
        "status": "ok" if sys.version_info >= (3, 11) else "failed",
        "detail": f"{sys.executable} {sys.version.split()[0]}",
    }]
    ok, detail = check_command([sys.executable, "-c", "import mlx_whisper; print('mlx_whisper ok')"])
    checks.append({"name": "MLX Whisper", "status": "ok" if ok else "failed", "detail": detail})

    # WeWe RSS: reachable AND fresh (a frozen-but-reachable bridge is NOT healthy)
    auth_issue = wewe_auth_problem()
    reachable, detail = check_command(["/usr/bin/curl", "-fsS", "http://localhost:4000/feeds/MP_WXS_3223096120.json"])
    frozen = [v["name"] for v in by_platform("wechat") if v.get("state") == "STALE"]
    if auth_issue:
        checks.append(auth_issue)
    elif not reachable:
        checks.append({"name": "WeWe RSS", "status": "failed", "detail": f"bridge 不可达：{detail}"})
    elif frozen:
        checks.append({"name": "WeWe RSS", "status": "stale", "detail": f"bridge 可达，但 {len(frozen)} 个公众号 feed 冻结（需重登微信读书）：{'、'.join(frozen[:4])}"})
    else:
        checks.append({"name": "WeWe RSS", "status": "ok", "detail": "localhost:4000 可达，feed 新鲜"})

    ok, detail = check_command([
        sys.executable, "-c",
        "import sys; from pathlib import Path; sys.path.insert(0, str(Path.home()/'content-toolkit/capabilities/download')); "
        "from content_downloader.adapters.douyin.api_client import DouyinAPIClient; print('ok')",
    ])
    checks.append({"name": "抖音下载器", "status": "ok" if ok else "failed",
                   "detail": "api_client 可导入" if ok else f"导入失败（content-toolkit 已 archive？）：{detail}"})

    # 抖音 Cookie: FUNCTIONAL — did recent douyin fetches actually succeed?
    dy_down = [v["name"] for v in by_platform("douyin") if v.get("state") == "DOWN"]
    if not cookie.exists():
        checks.append({"name": "抖音 Cookie", "status": "failed", "detail": "cookie 文件缺失"})
    elif dy_down:
        checks.append({"name": "抖音 Cookie", "status": "failed", "detail": f"{len(dy_down)} 个抖音号最近抓取报错（cookie 过期/风控）：{'、'.join(dy_down[:4])}"})
    else:
        checks.append({"name": "抖音 Cookie", "status": "ok", "detail": "cookie 存在，最近抓取正常"})

    # X 登录态: FUNCTIONAL — did recent X fetches actually succeed?
    tw = by_platform("twitter")
    tw_down = [v["name"] for v in tw if v.get("state") == "DOWN"]
    if not twitter_auth.exists():
        checks.append({"name": "X 登录态", "status": "failed", "detail": "twitter-auth.env 缺失"})
    elif tw and len(tw_down) == len(tw):
        checks.append({"name": "X 登录态", "status": "failed", "detail": f"全部 {len(tw)} 个 X 账号抓取失败（登录态可能过期）"})
    elif tw_down:
        checks.append({"name": "X 登录态", "status": "stale", "detail": f"{len(tw_down)} 个 X 账号抓取报错：{'、'.join(tw_down[:4])}"})
    else:
        checks.append({"name": "X 登录态", "status": "ok", "detail": "twitter-auth.env 可用，最近抓取正常"})

    yt_failures = media_failures_for_date(today())
    if yt_failures:
        checks.append({
            "name": "YouTube Cookie",
            "status": "failed",
            "detail": f"{len(yt_failures)} 条 YouTube/音视频转录失败；可能需要更新 youtube-cookies.txt",
        })
    return checks


def blocking_dependency_rows(deps: list[dict]) -> list[dict]:
    rows = []
    for row in deps:
        name = str(row.get("name") or "")
        if row.get("status") != "ok" and any(token in name for token in BLOCKING_DEP_TOKENS):
            rows.append(row)
    return rows


def render_blocking_dependency_alert(rows: list[dict]) -> str:
    if not rows:
        return ""
    items = "".join(
        f"<li><strong>{escape(str(row.get('name') or '依赖'))}</strong>：{escape(str(row.get('detail') or row.get('status') or '异常'))}</li>"
        for row in rows
    )
    script_url = "file://" + str(MANUAL_PUSH_SCRIPT)
    notify_body = "；".join(str(row.get("name") or "依赖异常") for row in rows[:3])
    return f"""
    <section class="auth-alert manual-alert">
      <div class="auth-copy">
        <span class="alert-kicker">定时推送已暂停</span>
        <h2>公众号或 YouTube 需要手动恢复</h2>
        <p>9 点定时推送遇到可恢复依赖异常时会先暂停，避免发出缺内容的日报。恢复登录态或 cookies 后，点击下面的按钮手动跑完整流程。</p>
        <ul>{items}</ul>
        <div class="pill-row">
          <a class="auth-button" href="{escape(script_url)}">手动推送</a>
          <span class="pill">脚本位置：{escape(str(MANUAL_PUSH_SCRIPT))}</span>
        </div>
      </div>
      <div class="auth-qr auth-action">
        <strong>Manual Push</strong>
        <span>fetch → process → newsletter</span>
      </div>
    </section>
    <script>
    (function() {{
      var body = {json.dumps(notify_body, ensure_ascii=False)};
      if (!("Notification" in window)) return;
      function send() {{ try {{ new Notification("Daily Inbox 需要维护", {{ body: body }}); }} catch (e) {{}} }}
      if (Notification.permission === "granted") send();
      else if (Notification.permission !== "denied") Notification.requestPermission().then(function(p) {{ if (p === "granted") send(); }});
    }})();
    </script>
    """


def status_label(status: str) -> str:
    return {
        "ok_new": "有新增",
        "ok_no_new": "成功无新增",
        "filtered_out": "抓到但过滤",
        "stale": "上游冻结",
        "failed": "抓取失败",
        "not_checked_due_timeout": "超时未检查",
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
    if status == "stale":
        return "上游 feed 冻结"
    if status == "failed":
        return "抓取失败"
    if status == "not_checked_due_timeout":
        return "超时未检查"
    return "其他状态"


def manual_links_summary() -> dict:
    state = load_json(ROOT / "state.json").get("manual-links", {})
    manual_file = PARKIO / "_inbox" / "manual-links.md"
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
    for path in sorted(SENT_DIR.glob("*.md")):
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
    path = SENT_DIR / f"{short_day}.md"
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
    root = PARKIO / "002_个人收藏"
    by_source: dict[str, dict] = {}
    if not root.exists():
        return []

    article_paths = [
        path
        for path in root.rglob("*.md")
        if path.is_file() and "_gotchas" not in path.parts and path.name != "profile.md"
    ]
    # Source profile baselines are operational data, not Obsidian references.
    article_paths.extend(PROFILE_LIBRARY_DIR.glob("*/items/*.md"))
    article_paths.extend(PROFILE_LIBRARY_DIR.glob("*/items/*/article.md"))

    for article in article_paths:
        fm, _body = item_frontmatter(article)
        source = str(fm.get("source_name") or fm.get("profile_name") or fm.get("profile_id") or "library")
        row = by_source.setdefault(
            source,
            {"profile": source, "total": 0, "selected": 0, "channels": Counter(), "latest": "", "latest_time": "-"},
        )
        url = str(fm.get("url", ""))
        row["total"] += 1
        row["channels"][str(fm.get("channel") or fm.get("platform") or channel_for_url(url))] += 1
        if url and url in pushed:
            row["selected"] += 1
        mtime = article.stat().st_mtime
        current_latest = row.get("_latest_mtime", 0.0)
        if mtime > current_latest:
            row["_latest_mtime"] = mtime
            row["latest"] = title_from_article(article)
            row["latest_time"] = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")

    rows = []
    for row in by_source.values():
        total = row["total"]
        rows.append(
            {
                "profile": row["profile"],
                "total": total,
                "selected": row["selected"],
                "rate": (row["selected"] / total * 100) if total else 0,
                "channels": dict(row["channels"]),
                "latest": row["latest"],
                "latest_time": row["latest_time"],
            }
        )
    return sorted(rows, key=lambda item: item["total"], reverse=True)


def independent_link_count() -> int:
    return sum(
        1
        for path in (PARKIO / "002_个人收藏").glob("*.md")
        if path.is_file() and "profile_id: x-saved" in path.read_text(encoding="utf-8", errors="replace")[:500]
    )


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
            "你主动收藏、点赞或贴到 manual-links 的内容；默认进入正文或个人收藏。",
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


def render_scoring_banner() -> str:
    """Surface a scoring outage on the owner page (gotcha #21). score-items
    writes scoring-health.json; only degraded/outage states show a banner."""
    data = load_json(ROOT / "scoring-health.json")
    status = data.get("status")
    if status not in ("outage", "degraded"):
        return ""
    failed = data.get("failed_batches", 0)
    total = data.get("total_batches", 0)
    scored = data.get("scored_items", 0)
    queued = data.get("queued_items", 0)
    color = "#be123c" if status == "outage" else "#b45309"
    label = "评分服务中断" if status == "outage" else "评分部分降级"
    return f"""
    <section class="panel" style="border-left:6px solid {color};background:#fff7f5">
      <h2 style="color:{color}">⚠ {escape(label)}</h2>
      <p>评分服务今天有 {failed}/{total} 批失败（{scored}/{queued} 条完成评分）。
      官方 / 手动 / 媒体内容仍照常进入正文（它们不依赖评分）；普通 X feed 可能缺失——
      这是评分中断，不是今天没有内容。</p>
    </section>"""


def render_path_breakdown(breakdown: dict) -> str:
    """Detailed per-path funnel for the owner page: per-channel fetched→kept,
    merged events, and the configured channels that had no update today."""
    blocks = []
    for i, p in enumerate(breakdown["paths"], 1):
        if p["bypass"]:
            funnel = f"{p['channels_updated']}/{p['channels_total']} 渠道更新 · 抓取 {p['fetched']} · 全部收录（不过滤）"
        else:
            funnel = (
                f"{p['channels_updated']}/{p['channels_total']} 渠道 · 抓取 {p['fetched']} · "
                f"进正文 {p['kept']} · 过滤 {p['filtered']}"
            )
        if p["events"]:
            cap = f"（正文展开前 {p['rendered']}）" if p["events"] > p["rendered"] else ""
            funnel += f" · 合并 {p['events']} 事件{cap}"

        rows = ""
        channels = sorted(
            p["channels"].items(),
            key=lambda kv: -(kv[1]["fetched"] - kv[1]["kept"]) if not p["bypass"] else -kv[1]["fetched"],
        )
        for name, c in channels:
            filt = c["fetched"] - c["kept"]
            rows += (
                f"<tr><td>{escape(name)}</td><td>{c['fetched']}</td><td>{c['kept']}</td>"
                f"<td>{filt if not p['bypass'] else '—'}</td></tr>"
            )
        table = (
            f"<table class='mini'><thead><tr><th>渠道</th><th>抓取</th><th>进正文</th><th>过滤</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
            if rows else "<p style='color:#94a3b8'>今日无更新</p>"
        )
        silent = ""
        if p["silent"]:
            names = "、".join(escape(n) for n in p["silent"])
            silent = f"<p style='color:#94a3b8;font-size:14px'>无更新渠道（{len(p['silent'])}）：{names}</p>"
        blocks.append(
            f"<div class='path-block'><h3>P{i} · {escape(p['label'])}</h3>"
            f"<p class='path-funnel'>{funnel}</p>{table}{silent}</div>"
        )
    kept_total = sum(p["kept"] for p in breakdown["paths"])
    return f"""
    <section class="panel">
      <h2>四条路径漏斗</h2>
      <p>每条 path 规则不同：官方 / 音视频 / 收藏不按评分过滤，只有 X 应用层走评分门。
      合计 {breakdown['total']} 条抓取 → {kept_total} 条进入正文。</p>
      {''.join(blocks)}
    </section>"""


def render() -> str:
    date = today()
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    scores = summarize.load_scores()
    sources_today, _ = summarize.read_today_items(date, scores)
    health = summarize.source_health(sources_today, date)
    active_report = build_run_report(sources_today, health, date)
    if active_report.get("mode") == "batch":
        write_run_report(active_report)
    digest_report = active_report if active_report.get("mode") == "batch" else latest_run_report(date)
    report_for_header = digest_report or active_report
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
    report_health = report_for_header.get("health", {})
    report_totals = report_for_header.get("totals", {})
    report_problem_count = int(report_health.get("needs_attention", 0) or 0)
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

    deps = dependency_checks()
    blocking_deps = blocking_dependency_rows(deps)
    dependency_rows = []
    for row in deps:
        dependency_rows.append(
            f"<tr><td>{escape(row['name'])}</td><td><span class='status {escape(row['status'])}'>{'正常' if row['status'] == 'ok' else '异常'}</span></td><td>{escape(row['detail'])}</td></tr>"
        )

    report_problem_rows = []
    for row in report_health.get("source_problems", []):
        report_problem_rows.append(
            f"<tr><td>来源异常</td><td>{escape(row.get('name', ''))}</td><td>{escape(row.get('detail', row.get('status', '')))}</td></tr>"
        )
    for row in report_health.get("media_failures", []):
        report_problem_rows.append(
            f"<tr><td>音视频转录</td><td>{escape(row.get('source', ''))}：{escape(row.get('title', ''))}</td><td>{escape(row.get('error', ''))}</td></tr>"
        )
    if report_health.get("scoring"):
        scoring = report_health["scoring"]
        report_problem_rows.append(
            f"<tr><td>打分服务</td><td>{escape(str(scoring.get('status', '')))}</td><td>{escape(str(scoring.get('message', '')))}</td></tr>"
        )
    reader_quality = report_health.get("reader_quality") or {}
    reader_quality_status = str(reader_quality.get("status") or "未运行")
    for row in reader_quality.get("issues", []) or []:
        report_problem_rows.append(
            f"<tr><td>读者 QA / {escape(str(row.get('severity', '')))}</td><td>{escape(str(row.get('artifact', '')))}</td><td>{escape(str(row.get('message', '')))}</td></tr>"
        )
    feishu_status = report_health.get("feishu") or {}
    if feishu_status:
        report_problem_rows.append(
            f"<tr><td>飞书发送</td><td>{escape(str(feishu_status.get('status', '')))}</td><td>{escape(str(feishu_status.get('chunks', 0)))} 段 · {escape(str(feishu_status.get('chars', 0)))} 字</td></tr>"
        )

    profile_rows = []
    for row in sorted(profile_stats, key=lambda value: (-value["total"], value["profile"]))[:50]:
        channels = " / ".join(f"{k} {v}" for k, v in sorted(row["channels"].items()))
        profile_rows.append(
            f"<tr><td>{escape(row['profile'])}</td><td>{row['total']}</td><td>{row['selected']}</td><td>{row['rate']:.0f}%</td><td>{escape(channels)}</td><td>{escape(row['latest_time'])}</td><td>{escape(row['latest'][:80])}</td></tr>"
        )

    sections = "、".join(sent["sections"]) if sent["sections"] else "尚未生成今日推送"
    today_verdict = "今日推送已完成" if sent["exists"] else "今日尚未推送"
    if report_problem_count:
        today_verdict += f"；{report_problem_count} 个问题需要维护"
    elif funnel["total"] == 0:
        today_verdict += "；暂无新增 raw input"
    else:
        today_verdict += "；来源健康无阻塞"
    digest_label = report_for_header.get("batch_label", "尚无日报 batch")
    digest_items = int(report_totals.get("items", 0) or 0)
    digest_kept = int(report_totals.get("kept", 0) or 0)
    digest_filtered = int(report_totals.get("filtered", 0) or 0)
    report_funnel = report_for_header.get("funnel") or {}
    digest_ai_input = int(report_funnel.get("ai_input_items", 0) or report_totals.get("processed_markdown_files", 0) or 0)
    digest_events = int(report_totals.get("events", 0) or 0)
    digest_brief = int(report_totals.get("brief_universe", 0) or 0)
    digest_deep = int(report_totals.get("deep_candidates", 0) or 0)
    digest_coarse_rejects = int(report_totals.get("coarse_rejects", 0) or 0)
    digest_pending_raw = int(report_totals.get("pending_raw", 0) or 0)
    digest_pending_x_saved_raw = int(report_totals.get("pending_x_saved_raw", 0) or 0)
    mode_note = (
        f"当前页面基于最新日报 batch {digest_label}；下方另列当前 unprocessed 下一批。"
        if active_report.get("mode") != "batch" and digest_report
        else f"当前页面基于正在处理的 batch {active_report.get('batch_label')}。"
    )
    write_live_dashboard_payload(
        {
            "schema": 2,
            "generatedAt": datetime.now().isoformat(timespec="seconds"),
            "sourceHealthDate": date,
            "batch": {
                "label": digest_label,
                "mode": report_for_header.get("mode"),
                "dir": report_for_header.get("batch_dir"),
            },
            "funnel": {
                "aiInputItems": digest_ai_input,
                "coarseRejects": digest_coarse_rejects,
                "events": digest_events,
                "briefUniverse": digest_brief,
                "deepCandidates": digest_deep,
                "filtered": digest_filtered,
                "pendingRaw": digest_pending_raw,
                "pendingXSavedRaw": digest_pending_x_saved_raw,
            },
            "readerQuality": reader_quality,
            "feishu": feishu_status,
            "health": {
                "needsAttention": report_problem_count,
                "sourceProblems": report_health.get("source_problems") or [],
                "dependencies": report_health.get("dependencies") or [],
                "mediaFailures": report_health.get("media_failures") or [],
            },
            "sent": {**sent, "path": str(sent.get("path") or "")},
        }
    )
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
    .auth-alert {{ display: grid; grid-template-columns: 1fr 210px; gap: 20px; align-items: center; background: #fff4ed; border: 1px solid #ffb892; border-left: 5px solid #c2410c; border-radius: 10px; padding: 18px; margin: 0 0 18px; }}
    .auth-alert h2 {{ margin: 4px 0 8px; color: #8a2c0b; font-size: 22px; }}
    .auth-alert p {{ color: #684234; }}
    .auth-alert ul {{ margin: 10px 0 0; padding-left: 18px; color: #4a2e24; }}
    .alert-kicker {{ color: #b42318; font-weight: 800; font-size: 12px; letter-spacing: .08em; }}
    .auth-button {{ display: inline-flex; align-items: center; justify-content: center; min-height: 32px; padding: 6px 12px; border-radius: 999px; background: #8a2c0b; color: #fff; text-decoration: none; font-weight: 700; font-size: 13px; }}
    .auth-qr {{ display: grid; place-items: center; min-height: 180px; background: #fff; border: 1px solid #f6c7ad; border-radius: 8px; }}
    .auth-qr img {{ width: 168px; height: 168px; object-fit: contain; }}
    .auth-action strong, .auth-action span {{ display: block; text-align: center; }}
    .auth-action strong {{ color: #8a2c0b; font-size: 18px; }}
    .auth-action span {{ color: #684234; font-size: 12px; margin-top: 4px; }}
    .pill-row {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }}
    .pill {{ border: 1px solid var(--line); border-radius: 999px; padding: 4px 9px; background: #fafaf6; color: #46554e; font-size: 12px; }}
    @media (max-width: 980px) {{ .hero, .visual-grid, .grid, .grid.two, .workflow, .intake-row, .auth-alert {{ grid-template-columns: 1fr; }} .flow-arrow {{ display: none; }} main {{ width: min(100% - 20px, 1180px); }} .donut-wrap {{ grid-template-columns: 1fr; }} .funnel-slice {{ width: 100% !important; min-width: 0; }} .sub-grid {{ grid-template-columns: 1fr; }} .section-head {{ display: block; }} .output-badge {{ margin-top: 10px; text-align: left; }} }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Daily Inbox 内部状态面板</h1>
      <p>生成时间：{escape(generated)} · 日期：{escape(date)} · 这个页面面向维护者，用来检查抓取、筛选、推送和长期资料库。</p>
    </header>

    {render_wewe_auth_alert()}
    {render_blocking_dependency_alert(blocking_deps)}

    <section class="hero">
      <div class="hero-summary">
        <h2>{escape(today_verdict)}</h2>
        <p>最新日报 batch：AI 输入 {digest_ai_input} 条，粗筛丢弃 {digest_coarse_rejects} 条，合并 {digest_events} 个事件，快讯 {digest_brief} 条，深读 {digest_deep} 条；pending raw {digest_pending_raw} 条（X 收藏 {digest_pending_x_saved_raw} 条）；读者 QA：{escape(reader_quality_status)}；飞书：{escape(str(feishu_status.get('status') or '未发送'))}。{escape(mode_note)}</p>
        <div class="pill-row">
          <span class="pill">下一次推送 {escape(next_push_text())}</span>
          <span class="pill">手动链接待导入 {manual['pending']}</span>
          <span class="pill">需维护 {report_problem_count}</span>
          <span class="pill">Reader QA {escape(reader_quality_status)}</span>
          <span class="pill">Feishu {escape(str(feishu_status.get('status') or '未发送'))}</span>
          <span class="pill">Pending raw {digest_pending_raw} · X 收藏 {digest_pending_x_saved_raw}</span>
        </div>
      </div>
      {render_donut("今日内容去向", today_parts, max(funnel["total"], 0), "条原始内容")}
    </section>

    {render_scoring_banner()}

    <section class="grid">
      {render_metric("活跃来源", len(configured), "来源清单中启用的来源")}
      {render_metric("最新日报 Batch", digest_items, f"事件 {digest_events} · 快讯 {digest_brief} · 深读 {digest_deep}")}
      {render_metric("Pending Raw", digest_pending_raw, f"X 收藏 {digest_pending_x_saved_raw} · 等待下一轮 to_md")}
      {render_metric("当前待处理（下一批）", funnel["total"], f"进入正文 {funnel['kept']} · 过滤 {funnel['filtered']}")}
      {render_metric("今日已推送", pushed_count, "Telegram 推送链接数")}
      {render_metric("需要维护", report_problem_count, "来自最新日报 batch 的 health report")}
    </section>

    {render_intake_funnel(intake_buckets, pushed_count)}

    {render_path_breakdown(summarize.compute_path_breakdown(sources_today))}

    <h2>今日处理总览</h2>
    <section class="visual-grid">
      {render_funnel(funnel["total"], funnel["kept"], funnel["filtered"], pushed_count)}
      {render_donut("来源健康分布", health_parts, len(health), "个来源")}
    </section>

    <details open>
      <summary>最新日报 Health Report</summary>
      <table>
        <thead><tr><th>类型</th><th>对象</th><th>说明</th></tr></thead>
        <tbody>{render_rows(report_problem_rows)}</tbody>
      </table>
    </details>

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
        <p><strong>读者 QA：</strong>{escape(reader_quality_status)}</p>
        <p><strong>飞书：</strong>{escape(str(feishu_status.get('status') or '未发送'))}</p>
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
    out = PARKIO / "_inbox" / "status.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
