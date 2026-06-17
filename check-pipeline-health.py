#!/usr/bin/env python3
"""Daily pipeline health check (gotcha #21/#23).

Runs after the morning digest is expected to be sent (scheduled ~10:00, well
after the slow v4-pro run finishes ~09:10). Alerts the owner via Telegram when:
  1. today's digest was NOT sent (and push-digest is not still running), or
  2. a source FAILED to fetch today, or
  3. a source has not fetched successfully in 7 days (likely broken), or
  4. the WeChat RSS bridge (wewe-rss / colima) is unreachable — public-account
     sources go silent when it's down (gotcha #23).

Silent success (fetched OK, no new items) is normal and does NOT alert.
"""
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime

from lib import PARKIO, ROOT, load_sources, today, write_health_alert
from run_report import latest_run_report, problem_lines

PUSH_LOG = ROOT / "logs" / "push-digest.log"
MEDIA_SUMMARIES = ROOT / "media-summaries.json"
SCORING_HEALTH = ROOT / "scoring-health.json"
WEWE_AUTH_ALERT = PARKIO / "_inbox" / "wewe-auth-alert.json"


def channel_health_rows() -> list[dict]:
    """Current per-source truth from fetch logs.

    James must not infer health from status.html or stale SLA rollups. The
    source of truth is the latest channel-health classification, which separates
    DOWN/STALE from a healthy QUIET source.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("channel_health", ROOT / "channel-health.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load channel-health.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.channel_rows()


def refresh_wewe_auth_state() -> None:
    """Refresh WeWe account state before judging it.

    The status page and wewe-auth-alert.json are render artifacts. A health check
    should probe the bridge/account directly first, then read the sidecar.
    """
    script = ROOT / "wewe-auth-monitor.py"
    if not script.exists():
        return
    subprocess.run(
        [sys.executable, str(script)],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=20,
        check=False,
    )


def failed_transcriptions() -> list[str]:
    """Curated videos whose transcription errored today (e.g. ReadTimeout).

    The owner expects every curated video to be fetched AND transcribed; a
    transcription error must surface, not vanish. status=='failed' is a transient
    error worth flagging; 'no_transcript'/'skipped_*' are settled outcomes."""
    if not MEDIA_SUMMARIES.exists():
        return []
    try:
        cache = json.loads(MEDIA_SUMMARIES.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    out = []
    for rec in cache.values() if isinstance(cache, dict) else []:
        if not isinstance(rec, dict) or rec.get("status") != "failed":
            continue
        if str(rec.get("updated_at", ""))[:10] != today():
            continue
        title = rec.get("title") or rec.get("url", "")
        out.append(f"{rec.get('source', '?')}：{title}（转录失败：{rec.get('error', '未知')[:60]}）")
    return out


def scoring_outage() -> str | None:
    """LLM scoring outage surfaced by score-items.py (scoring-health.json)."""
    if not SCORING_HEALTH.exists():
        return None
    try:
        h = json.loads(SCORING_HEALTH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if h.get("date") != today():
        return None  # stale file; today's scoring hasn't run / will be checked elsewhere
    if h.get("status") != "ok" or int(h.get("failed_batches", 0) or 0) > 0:
        return f"打分 LLM 异常（{h.get('failed_batches', '?')} 个批次失败，status={h.get('status')}）— 检查 DeepSeek/fallback"
    return None


def wewe_auth_issue() -> str | None:
    """WeWe bridge is reachable but the reader account itself is invalid."""
    if not WEWE_AUTH_ALERT.exists():
        return None
    try:
        data = json.loads(WEWE_AUTH_ALERT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if data.get("status") == "invalid":
        names = "、".join(str(row.get("name") or "未知账号") for row in data.get("invalid_accounts", [])[:4])
        return f"公众号登录态失效（{names or 'WeWe 读书账号'}）— 打开 inbox/status.html 扫码重新登录"
    if data.get("status") == "failed":
        return f"公众号登录态检测失败（{data.get('error', '未知错误')}）"
    return None


def digest_sent_today() -> bool:
    sent = PARKIO / "_inbox" / "sent" / f"{today()[2:]}.md"
    sent_full = PARKIO / "_inbox" / "sent" / f"{today()}.md"
    return sent.exists() or sent_full.exists()


def push_still_running(max_age_min: int = 90) -> bool:
    """True only if a push-digest run started recently (< max_age_min) and has
    no DONE yet — i.e. the slow v4-pro run is genuinely still in progress. An
    old START with no DONE means it hung/crashed, which SHOULD alert."""
    if not PUSH_LOG.exists():
        return False
    lines = PUSH_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    last_start_idx = last_start_ts = None
    for i, line in enumerate(lines):
        if "push-digest START" in line:
            last_start_idx, last_start_ts = i, _line_ts(line)
    if last_start_idx is None:
        return False
    done_after = any("push-digest DONE" in l for l in lines[last_start_idx:])
    if done_after:
        return False
    if last_start_ts is None:
        return False
    age_min = (datetime.now() - last_start_ts).total_seconds() / 60
    return 0 <= age_min < max_age_min


def _line_ts(line: str):
    m = re.search(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})", line)
    if not m:
        return None
    try:
        return datetime.strptime(f"{m.group(1)} {m.group(2)}", "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def broken_sources() -> list[str]:
    """Sources that are currently DOWN/STALE/UNKNOWN.

    Older versions also used source-health's 7-day SLA counters. Those counters
    can go stale or disagree with today's fetch logs, producing false alarms like
    "X source has not succeeded in 7 days" while channel-health shows it fetched
    today. Current truth wins.
    """
    problems = []
    for row in channel_health_rows():
        name = row.get("name", "?")
        state = row.get("state")
        if state == "DOWN":
            problems.append(f"{name}（今日抓取失败：{row.get('error') or 'fetch 报错'}）")
        elif state == "STALE":
            age = row.get("feed_age_days")
            detail = f"上游 feed 冻结（最新 {age}d 前）" if age and age != 9999 else "上游 feed 空/冻结"
            problems.append(f"{name}（{detail}）")
        elif state == "UNKNOWN":
            problems.append(f"{name}（最近一轮 fetch 未出现）")
    return problems


def wechat_bridge_down() -> str | None:
    """If WeChat sources rely on a local RSS bridge (wewe-rss on colima), probe
    it. When the bridge is down (e.g. colima not started after a reboot), all
    public-account feeds go silent — alert instead of failing quietly."""
    feed = None
    try:
        for row in load_sources():
            m = re.search(r"rss_url\s+(\S+)", row.get("notes", ""))
            if m:
                feed = m.group(1)
                break
    except Exception:
        return None
    if not feed:
        return None
    # Probe the bridge HOST (its dashboard), not one feed — a single feed 404 is
    # a per-account issue, not the bridge being down.
    host = feed.split("/feeds")[0].rstrip("/")
    req = urllib.request.Request(f"{host}/dash", headers={"User-Agent": "parkio-health/1"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            resp.read(1)
        return None
    except urllib.error.HTTPError:
        return None  # host responded (even 401/404) → bridge is up
    except Exception:
        return f"微信 RSS bridge 不可达（{host}）— 公众号源已停摆，检查 colima / wewe-rss"


def main() -> int:
    problems: list[str] = []
    try:
        refresh_wewe_auth_state()
    except Exception as exc:
        problems.append(f"公众号登录态检测刷新失败（{type(exc).__name__}: {exc}）")
    report = latest_run_report(today())

    if not digest_sent_today():
        if push_still_running():
            print("[health] digest not yet sent but push-digest is running — no alert")
        else:
            problems.append("今日简报未发送（push-digest 未完成或失败）")

    if report:
        problems.extend(problem_lines(report))
        wewe = wewe_auth_issue()
        if wewe and not any("公众号登录态" in p for p in problems):
            problems.append(wewe)
    else:
        try:
            problems.extend(broken_sources())
        except Exception as exc:  # never let source-health crash the check
            print(f"[health] source check skipped: {type(exc).__name__}: {exc}", file=sys.stderr)

        bridge = wechat_bridge_down()
        if bridge:
            problems.append(bridge)
        wewe = wewe_auth_issue()
        if wewe:
            problems.append(wewe)

        try:
            problems.extend(failed_transcriptions())
        except Exception as exc:
            print(f"[health] transcription check skipped: {type(exc).__name__}: {exc}", file=sys.stderr)

        scoring = scoring_outage()
        if scoring:
            problems.append(scoring)

    if not problems:
        # Heartbeat so the owner can see the check actually ran and found nothing.
        write_health_alert("✅ 一切正常（简报已生成，无异常渠道）")
        print(f"[health] OK {today()} — digest sent, no broken sources")
        return 0

    wrote = write_health_alert(f"⚠️ {len(problems)} 个问题需处理", problems)
    print(f"[health] {len(problems)} problem(s); local alert {'written' if wrote else 'FAILED to write'}")
    for p in problems:
        print(f"  - {p}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
