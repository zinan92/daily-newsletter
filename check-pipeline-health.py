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
import sys
import urllib.error
import urllib.request
from datetime import datetime

from lib import PARKIO, ROOT, load_sources, send_telegram, today

PUSH_LOG = ROOT / "logs" / "push-digest.log"
MEDIA_SUMMARIES = ROOT / "media-summaries.json"
SCORING_HEALTH = ROOT / "scoring-health.json"


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


def digest_sent_today() -> bool:
    sent = PARKIO / "inbox" / "sent" / f"{today()[2:]}.md"
    sent_full = PARKIO / "inbox" / "sent" / f"{today()}.md"
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
    """Sources that failed today or haven't succeeded in 7 days."""
    import summarize  # imported lazily; heavy module

    scores = summarize.load_scores()
    sources, _ = summarize.read_today_items(today(), scores)
    problems = []
    for row in summarize.source_health(sources, today()):
        name = row.get("name", "?")
        if row.get("status") == "failed":
            problems.append(f"{name}（今日抓取失败）")
        elif row.get("status") == "stale":
            # Bridge answers but the upstream feed is frozen (e.g. wewe-rss stopped
            # updating this account). It LOOKS green but silently stops delivering.
            problems.append(f"{name}（上游 feed 冻结：{row.get('detail', '最新文章过旧')}）")
        elif row.get("success_total_7d", 0) >= 3 and row.get("success_ok_7d", 0) == 0:
            problems.append(f"{name}（7 天未成功抓取，可能已坏）")
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

    if not digest_sent_today():
        if push_still_running():
            print("[health] digest not yet sent but push-digest is running — no alert")
        else:
            problems.append("今日简报未发送（push-digest 未完成或失败）")

    try:
        problems.extend(broken_sources())
    except Exception as exc:  # never let source-health crash the check
        print(f"[health] source check skipped: {type(exc).__name__}: {exc}", file=sys.stderr)

    bridge = wechat_bridge_down()
    if bridge:
        problems.append(bridge)

    try:
        problems.extend(failed_transcriptions())
    except Exception as exc:
        print(f"[health] transcription check skipped: {type(exc).__name__}: {exc}", file=sys.stderr)

    scoring = scoring_outage()
    if scoring:
        problems.append(scoring)

    if not problems:
        print(f"[health] OK {today()} — digest sent, no broken sources")
        return 0

    alert = "⚠️ Park-IO 管道告警 " + today() + "\n\n" + "\n".join(f"• {p}" for p in problems)
    sent = send_telegram(alert)
    print(f"[health] {len(problems)} problem(s); telegram alert {'sent' if sent else 'FAILED to send'}")
    for p in problems:
        print(f"  - {p}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
