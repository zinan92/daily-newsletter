#!/usr/bin/env python3
"""Record and render source-level fetch health.

This tracks fetch success only. It does not judge content quality.
"""
import argparse
import json
import sys
from datetime import datetime, timedelta

from lib import SOURCE_MANAGEMENT_DIR, ROOT, load_sources, load_state, today

HEALTH_JSON = ROOT / "source-health.json"
HEALTH_MD = SOURCE_MANAGEMENT_DIR / "source-health.md"


def source_key(src: dict) -> str:
    platform = src.get("platform", "")
    name = src.get("name", "")
    if platform == "twitter":
        handle = src.get("url", "").rstrip("/").split("/")[-1]
        return f"twitter:{handle}"
    if platform == "wechat" and "rss_url " in src.get("notes", ""):
        return f"wechat-rss:{name}"
    if platform in {"rss", "scrape", "wechat", "wechat-rss", "douyin"}:
        return f"{platform}:{name}"
    return f"{platform}:{name}"


def latest_error(component: str, needle: str = "") -> str:
    path = ROOT / "logs" / f"{component}.log"
    if not path.exists():
        return ""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    for line in reversed(lines[-800:]):
        if needle and needle not in line:
            continue
        if "ERROR" in line or "Traceback" in line or "ModuleNotFoundError" in line or "exit=" in line:
            return line.strip()[:260]
    return ""


def latest_timeout(component: str, day: str) -> str:
    paths = [
        ROOT / "logs" / f"{component}.log",
        ROOT / "logs" / "fetch.log",
        ROOT / "logs" / "fetch-all.log",
    ]
    for path in paths:
        if not path.exists():
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in reversed(lines[-800:]):
            if day in line and "timeout after" in line:
                return line.strip()[:260]
    return ""


def fetch_component(src: dict) -> str:
    platform = src.get("platform", "")
    if platform == "wechat" and "rss_url " in src.get("notes", ""):
        return "fetch-wechat-rss"
    if platform == "twitter":
        return "fetch-twitter"
    if platform == "rss":
        return "fetch-rss"
    if platform == "scrape":
        return "fetch-scrape"
    if platform == "wechat":
        return "fetch-wechat"
    if platform == "wechat-rss":
        return "fetch-wechat-rss"
    if platform == "douyin":
        return "fetch-douyin"
    return "fetch"


def classify_source(src: dict, st: dict, day: str) -> tuple[str, str]:
    """Decide (status, detail) for one source from today's recorded state.

    Pure and unit-testable. A source is only 'ok' if it ran today AND the
    fetcher did not record a failure — fetchers stamp ``last_fetch`` even when
    they error (e.g. WeChat RSS bridge Connection refused), so ``last_fetch``
    alone is a false-green signal (gotcha #23).
    """
    platform = src.get("platform", "")
    name = src.get("name", "")
    if platform not in {"twitter", "rss", "scrape", "wechat", "wechat-rss", "douyin"}:
        return "unsupported", f"platform={platform} is not fetched automatically"
    ran_today = st.get("last_fetch") == day
    recorded_failure = st.get("status") == "failed" or bool(st.get("error"))
    if ran_today and not recorded_failure:
        recorded_status = st.get("status")
        if platform == "twitter" and recorded_status in {"ok_new", "ok_no_new"}:
            return recorded_status, st.get("detail") or f"timeline checked; {st.get('new_count', 0)} new item(s)"
        if platform == "wechat-rss" or (platform == "wechat" and "rss_url " in src.get("notes", "")):
            return "ok", f"RSS/JSON bridge checked; {st.get('entries', 0)} entries, {st.get('imported', 0)} imported"
        if platform == "wechat":
            account = st.get("account", "")
            return "ok", f"seed article fetched into library; account={account or 'unknown'}"
        if platform == "douyin":
            count = st.get("profile_count")
            detail = f"profile checked for new videos; {count} public videos visible" if count else "profile checked for new videos"
            return "ok", detail
        return "ok", "fetch succeeded"
    component = fetch_component(src)
    if platform == "twitter":
        timeout = latest_timeout(component, day)
        if timeout and not ran_today:
            return "not_checked_due_timeout", f"X timeline fetch timed out before this source was checked: {timeout}"
    needle = f"@{src.get('url', '').rstrip('/').split('/')[-1]}" if platform == "twitter" else name
    detail = st.get("error") or latest_error(component, needle) or "no successful fetch today"
    return "failed", detail


def current_source_rows() -> list[dict]:
    state = load_state()
    day = today()
    rows = []
    for src in load_sources():
        st = state.get(source_key(src), {})
        status, detail = classify_source(src, st, day)
        rows.append(
            {
                "name": src.get("name", ""),
                "platform": src.get("platform", ""),
                "priority": src.get("priority", ""),
                "status": status,
                "detail": detail,
            }
        )
    rows.append(wechat_exporter_row(state, day))
    return rows


def wechat_exporter_row(state: dict, day: str) -> dict:
    st = state.get("wechat-exporter", {})
    if st.get("last_fetch") != day:
        status = "failed"
        detail = "wechat exporter bridge did not run today"
    elif st.get("status") == "not_configured":
        status = "not_configured"
        detail = f"export dir missing: {st.get('export_dir', '')}"
    elif st.get("status") == "empty":
        status = "ok_no_new"
        detail = f"export dir configured but empty: {st.get('export_dir', '')}"
    else:
        status = "ok"
        detail = f"{st.get('files', 0)} exported file(s), {st.get('imported', 0)} imported"
    return {
        "name": "WeChat Exporter Bridge",
        "platform": "wechat-exporter",
        "priority": "high",
        "status": status,
        "detail": detail,
    }


def load_history() -> dict:
    if not HEALTH_JSON.exists():
        return {"runs": []}
    try:
        data = json.loads(HEALTH_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"runs": []}
    if not isinstance(data, dict):
        return {"runs": []}
    data.setdefault("runs", [])
    return data


def save_history(data: dict) -> None:
    HEALTH_JSON.parent.mkdir(parents=True, exist_ok=True)
    HEALTH_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def prune_runs(runs: list[dict], days: int = 14) -> list[dict]:
    cutoff = datetime.now() - timedelta(days=days)
    out = []
    for run in runs:
        try:
            ts = datetime.fromisoformat(str(run.get("ts", "")))
        except ValueError:
            continue
        if ts >= cutoff:
            out.append(run)
    return out


def record() -> dict:
    rows = current_source_rows()
    data = load_history()
    runs = prune_runs(data.get("runs", []))
    runs.append(
        {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "date": today(),
            "sources": {row["name"]: row for row in rows},
        }
    )
    data["runs"] = runs[-120:]
    save_history(data)
    HEALTH_MD.parent.mkdir(parents=True, exist_ok=True)
    HEALTH_MD.write_text(render_markdown(data), encoding="utf-8")
    return data


def source_stats(data: dict, days: int = 7) -> dict[str, dict]:
    cutoff = datetime.now() - timedelta(days=days)
    stats: dict[str, dict] = {}
    for run in data.get("runs", []):
        try:
            ts = datetime.fromisoformat(str(run.get("ts", "")))
        except ValueError:
            continue
        if ts < cutoff:
            continue
        sources = run.get("sources", {})
        if not isinstance(sources, dict):
            continue
        for name, row in sources.items():
            stat = stats.setdefault(name, {"ok": 0, "total": 0, "last_status": "", "last_detail": ""})
            stat["total"] += 1
            if row.get("status") in {"ok", "ok_new", "ok_no_new"}:
                stat["ok"] += 1
            stat["last_status"] = row.get("status", "")
            stat["last_detail"] = row.get("detail", "")
    for stat in stats.values():
        total = stat["total"]
        stat["rate"] = round((stat["ok"] / total) * 100) if total else 0
    return stats


def render_markdown(data: dict) -> str:
    stats = source_stats(data)
    rows = current_source_rows()
    lines = [
        "# Source Health",
        "",
        "只记录抓取是否成功，不评价内容质量。",
        "",
        "| Source | Platform | Current | 7d Fetch Success | Detail |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        stat = stats.get(row["name"], {"ok": 0, "total": 0, "rate": 0})
        rate = f"{stat['rate']}% ({stat['ok']}/{stat['total']})" if stat["total"] else "n/a"
        detail = str(row["detail"]).replace("|", "/")
        lines.append(f"| {row['name']} | {row['platform']} | {row['status']} | {rate} | {detail} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    if args.record:
        data = record()
    else:
        data = load_history()
        if args.render:
            HEALTH_MD.write_text(render_markdown(data), encoding="utf-8")
    if args.render or args.record:
        print(HEALTH_MD)
    else:
        print(json.dumps(source_stats(data), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
