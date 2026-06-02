#!/usr/bin/env python3
"""Push only newly valuable Park-IO panel items to Telegram."""
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from lib import SENT_DIR, _load_secret, batch_artifact_paths, batch_label

# Telegram credentials load from env or ~/park-io/secrets/<file> — never
# hardcoded, so the (public) repo carries no bot token.
BOT_TOKEN = _load_secret("PARKIO_TELEGRAM_BOT_TOKEN", "telegram-bot-token")
CHAT_ID = _load_secret("PARKIO_TELEGRAM_CHAT_ID", "telegram-chat-id")
INBOX = Path.home() / "park-io" / "inbox"
PROCESSED_MD = INBOX / "processed_md"
PROCESSED_HTML = INBOX / "processed_html"
PROCESSED_PNG = INBOX / "processed_png"
STATE_FILE = Path(__file__).parent / "tg-push-state.json"
TG_LIMIT = 4000
PUSH_RE = re.compile(r"<!-- parkio-push-items:(.*?) -->", re.S)
PROCESSED_RE = re.compile(r"<!-- parkio-processed-items:(.*?) -->", re.S)
PUSH_SECTIONS = ("今日结论", "今日精选", "Podcast / YouTube / 抖音")
NUMBERED_EVENT_RE = re.compile(r"^\d+\.\s+(.+)$")
BOLD_LINK_EVENT_RE = re.compile(r"^\*\*(?:[^：:]{1,12}[：:])?\[([^\]]+)\]\(([^)]+)\)\*\*$")
BOLD_LINK_WITH_LABEL_RE = re.compile(r"^\*\*([^：:]{1,12})[：:]\[([^\]]+)\]\(([^)]+)\)\*\*$")
BULLET_BOLD_LINK_WITH_SUMMARY_RE = re.compile(r"^-\s+\*\*\[([^\]]+)\]\(([^)]+)\)\*\*[：:]\s*(.+)$")
BULLET_BOLD_TITLE_WITH_SUMMARY_RE = re.compile(r"^-\s+\*\*([^*]+)\*\*[：:]\s*(.+)$")


def send_multipart(url: str, fields: list[tuple[str, str]], file_field: str, path: Path, content_type: str) -> None:
    boundary = "----parkio-telegram-boundary"
    file_bytes = path.read_bytes()
    body = bytearray()
    for name, value in fields:
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(str(value).encode())
        body.extend(b"\r\n")
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(
        (
            f'Content-Disposition: form-data; name="{file_field}"; filename="{path.name}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode()
    )
    body.extend(file_bytes)
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())

    req = urllib.request.Request(
        url,
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        resp = r.read().decode()
        if '"ok":true' not in resp:
            raise RuntimeError(f"telegram multipart api error: {resp}")


def send(text: str) -> None:
    data = urllib.parse.urlencode(
        {
            "chat_id": CHAT_ID,
            "text": text,
            "disable_web_page_preview": "true",
        }
    ).encode()
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=15) as r:
        body = r.read().decode()
        if '"ok":true' not in body:
            raise RuntimeError(f"telegram api error: {body}")


def send_document(path: Path, caption: str) -> None:
    send_multipart(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument",
        [("chat_id", CHAT_ID), ("caption", caption)],
        "document",
        path,
        "text/html; charset=utf-8",
    )


def send_image_document(path: Path, caption: str) -> None:
    send_multipart(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument",
        [("chat_id", CHAT_ID), ("caption", caption)],
        "document",
        path,
        "image/png",
    )


def render_long_image(html_panel: Path) -> Path | None:
    out = html_panel.with_suffix(".png")
    out.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parent / "html-to-long-image.py"),
            str(html_panel),
            str(out),
            "--width",
            os.environ.get("PARKIO_SCREENSHOT_WIDTH", "1200"),
        ],
        capture_output=True,
        text=True,
        timeout=90,
    )
    if result.returncode != 0:
        if result.stdout.strip():
            print(result.stdout.strip())
        if result.stderr.strip():
            print(result.stderr.strip(), file=sys.stderr)
        return None
    return out if out.exists() else None


def panel_paths() -> tuple[Path, Path, Path | None, str]:
    md, html, png = batch_artifact_paths()
    return md, html, png, batch_label()


def move_sent_artifacts(panel: Path, html_panel: Path, image_panel: Path | None, label: str) -> None:
    SENT_DIR.mkdir(parents=True, exist_ok=True)
    dst = SENT_DIR / f"{label}.md"
    if panel.exists():
        if dst.exists():
            dst.unlink()
        panel.rename(dst)
        print(f"  moved sent artifact {dst.name}")
    for transient in (html_panel, image_panel):
        if transient and transient.exists():
            transient.unlink()
            print(f"  removed transient artifact {transient.name}")


def health_banner() -> str:
    """Compact channel-health alert prepended to the digest, so a dead/frozen channel
    is visible the moment you read the newsletter — not silently missing. Empty when
    all channels are healthy. Plain text (sendMessage uses no parse_mode)."""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "channel_health", str(Path(__file__).parent / "channel-health.py")
        )
        ch = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ch)
        rows = ch.channel_rows()
    except Exception:
        return ""
    down = [r["name"] for r in rows if r["state"] == "DOWN"]
    stale = [r["name"] for r in rows if r["state"] == "STALE"]
    if not down and not stale:
        return ""
    lines = ["⚠️ 渠道健康告警（获取层）"]
    if down:
        lines.append(f"🔴 挂了 {len(down)}：" + "、".join(down[:8]))
    if stale:
        lines.append(f"🟠 上游冻结 {len(stale)}：" + "、".join(stale[:8]))
    lines.append("· 这些渠道没有正常更新，详情见 status.html")
    return "\n".join(lines) + "\n\n———\n\n"


def deliver_artifacts(push_body: str, html_panel: Path, image_panel: Path | None, label: str) -> Path | None:
    push_body = health_banner() + push_body
    for i, part in enumerate(chunk(push_body), 1):
        send(part)
        print(f"  sent chunk {i}")
    if html_panel.exists():
        send_document(html_panel, f"Park-IO Daily HTML — {label}")
        print(f"  sent html {html_panel.name}")
        screenshot = image_panel if image_panel and image_panel.exists() else render_long_image(html_panel)
        if screenshot:
            send_image_document(screenshot, f"Park-IO Daily Long Image — {label}")
            print(f"  sent long image {screenshot.name}")
            return screenshot
        print("  long image render failed")
    else:
        print(f"  html not found: {html_panel}")
    return image_panel


def chunk(text: str, limit: int = TG_LIMIT) -> list[str]:
    if len(text) <= limit:
        return [text]
    out = []
    buf = ""
    pieces = re.split(r"(?=\n## |\n### |\n#### |\n##### )", text)
    for piece in pieces:
        if buf and len(buf) + len(piece) + 5 > limit:
            out.append(buf)
            buf = ""
        if len(piece) > limit:
            if buf:
                out.append(buf)
                buf = ""
            out.extend(split_long_piece(piece, limit))
            continue
        buf += piece
    if buf:
        out.append(buf)
    return out


def split_long_piece(text: str, limit: int) -> list[str]:
    parts = []
    current = ""
    for paragraph in text.split("\n\n"):
        block = paragraph if not current else "\n\n" + paragraph
        if current and len(current) + len(block) > limit:
            parts.append(current)
            current = paragraph
        else:
            current += block
    if current:
        parts.append(current)
    return parts


def section_title(section: str) -> str:
    return section.splitlines()[0].strip()


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def extract_push_items(body: str) -> list[str]:
    return extract_marker_items(body, PUSH_RE)


def extract_processed_items(body: str) -> list[str]:
    return extract_marker_items(body, PROCESSED_RE)


def extract_marker_items(body: str, pattern: re.Pattern) -> list[str]:
    m = pattern.search(body)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []
    return [str(x) for x in data if str(x).strip()]


def extract_push_body(body: str) -> str:
    visible = PROCESSED_RE.sub("", PUSH_RE.sub("", body)).strip()
    return compact_push_body(visible)


def mark_processed(state: dict, processed_items: list[str], pushed_items: list[str] | None = None) -> dict:
    processed = set(state.get("processed_urls", []))
    processed.update(url for url in processed_items if url)
    state["processed_urls"] = sorted(processed)
    if pushed_items is not None:
        pushed = set(state.get("pushed_urls", []))
        pushed.update(url for url in pushed_items if url)
        state["pushed_urls"] = sorted(pushed)
    return state


def compact_push_body(visible: str) -> str:
    lines = visible.splitlines()
    title = lines[0].strip() if lines else "# Park-IO Daily Summary"
    out = [title, ""]

    in_conclusion = False
    in_worth = False
    in_updates = False
    current_event = None
    current_summary = []

    def flush_event() -> None:
        nonlocal current_event, current_summary
        if not current_event:
            return
        summary = " ".join(current_summary).strip()
        summary = summary.replace("**", "")
        summary = re.sub(r"\s+", " ", summary)
        out.append(f"- {current_event}")
        if summary:
            out.append(f"  {summary}")
        current_event = None
        current_summary = []

    for raw in lines[1:]:
        line = raw.strip()
        if line == "## 今日结论":
            flush_event()
            in_conclusion = True
            in_worth = False
            in_updates = False
            out.extend(["## 今日结论"])
            continue
        if line in {"## 今日精选", "## 今日值得看"}:
            flush_event()
            in_conclusion = False
            in_worth = True
            in_updates = False
            out.extend(["", "## 今日精选"])
            continue
        if line in {"## Podcast / YouTube / 抖音", "## Podcast / YouTube / 抖音精选", "## Podcast / YouTube / 抖音更新"}:
            flush_event()
            in_conclusion = False
            in_worth = False
            in_updates = True
            out.extend(["", "## Podcast / YouTube / 抖音"])
            continue
        if line.startswith("## "):
            flush_event()
            in_conclusion = False
            in_worth = False
            in_updates = False
            continue
        if in_conclusion:
            if line.startswith("- "):
                out.append(line)
            continue
        if in_updates:
            if line.startswith("### ") or line.startswith("#### "):
                out.extend(["", line])
                continue
            if line and not line.startswith(("_", "**")):
                out.append(line)
                continue
            continue
        if not in_worth:
            continue
        if line.startswith("### "):
            flush_event()
            out.extend(["", line])
            continue
        if line.startswith("#### "):
            flush_event()
            out.append(line)
            continue
        if line == "**对你的价值：**":
            continue
        if line.startswith("##### "):
            flush_event()
            current_event = line.removeprefix("##### ").strip()
            continue
        bullet_link = BULLET_BOLD_LINK_WITH_SUMMARY_RE.match(line)
        if bullet_link:
            flush_event()
            title, url, summary = bullet_link.groups()
            current_event = f"**[{title}]({url})**"
            current_summary.append(summary)
            continue
        bullet_title = BULLET_BOLD_TITLE_WITH_SUMMARY_RE.match(line)
        if bullet_title:
            flush_event()
            title, summary = bullet_title.groups()
            current_event = f"**{title}**"
            current_summary.append(summary)
            continue
        bold_link = BOLD_LINK_WITH_LABEL_RE.match(line) or BOLD_LINK_EVENT_RE.match(line)
        if bold_link:
            flush_event()
            if len(bold_link.groups()) == 3:
                label, title, url = bold_link.groups()
                current_event = f"**{label}：[{title}]({url})**"
            else:
                title, url = bold_link.groups()
                current_event = f"**[{title}]({url})**"
            continue
        if line.startswith("**") and line.endswith("**") and len(line) > 4:
            flush_event()
            out.extend(["", line])
            continue
        numbered = NUMBERED_EVENT_RE.match(line)
        if numbered:
            flush_event()
            current_event = numbered.group(1).strip()
            continue
        if current_event and line and not line.startswith("_"):
            current_summary.append(line)
            continue

    flush_event()
    return "\n".join(out).strip()


def extract_push_body_legacy(body: str) -> str:
    visible = PUSH_RE.sub("", body).strip()
    sections = visible.split("\n## ")
    keep = [sections[0]]
    for section in sections[1:]:
        if section_title(section) in PUSH_SECTIONS:
            keep.append("## " + section)
    return "\n".join(keep).strip()


def main() -> int:
    panel, html_panel, image_panel, label = panel_paths()
    if not panel.exists():
        print(f"[push-telegram] no panel: {panel}")
        return 0

    if os.environ.get("PARKIO_SKIP_QUALITY") != "1":
        quality = subprocess.run(
            [sys.executable, str(Path(__file__).parent / "quality-check.py")],
            capture_output=True,
            text=True,
        )
        if quality.stdout.strip():
            print(quality.stdout.strip())
        if quality.stderr.strip():
            print(quality.stderr.strip(), file=sys.stderr)
        if quality.returncode != 0:
            print("[push-telegram] quality check failed, skipping push")
            return quality.returncode

    body = panel.read_text(encoding="utf-8")
    push_items = extract_push_items(body)
    processed_items = extract_processed_items(body)
    state = load_state()
    if not push_items:
        push_body = extract_push_body(body)
        if os.environ.get("PARKIO_PUSH_DRY_RUN") == "1":
            print(push_body)
            if html_panel.exists():
                print(f"\n[HTML attachment] {html_panel}")
                screenshot = render_long_image(html_panel)
                if screenshot:
                    print(f"[Long image attachment] {screenshot}")
            return 0
        print("[push-telegram] no high-value push items; sending daily digest anyway")
        image_panel = deliver_artifacts(push_body, html_panel, image_panel, label)
        state["last_pushed"] = panel.name
        if processed_items:
            mark_processed(state, processed_items)
            print(f"  marked {len(processed_items)} raw URL(s) processed")
        save_state(state)
        move_sent_artifacts(panel, html_panel, image_panel, label)
        return 0

    pushed = set(state.get("pushed_urls", []))
    force_push = os.environ.get("PARKIO_FORCE_PUSH") == "1"
    new_items = push_items if force_push else [url for url in push_items if url not in pushed]
    if not new_items:
        if processed_items:
            save_state(mark_processed(state, processed_items))
            print(f"[push-telegram] no new high-value URLs; marked {len(processed_items)} raw URL(s) processed")
            return 0
        print("[push-telegram] no new high-value URLs, skipping")
        return 0

    push_body = extract_push_body(body)
    if os.environ.get("PARKIO_PUSH_DRY_RUN") == "1":
        print(push_body)
        if html_panel.exists():
            print(f"\n[HTML attachment] {html_panel}")
            screenshot = render_long_image(html_panel)
            if screenshot:
                print(f"[Long image attachment] {screenshot}")
        return 0

    print(f"[push-telegram] pushing {len(new_items)} new high-value URL(s)")
    image_panel = deliver_artifacts(push_body, html_panel, image_panel, label)

    state["last_pushed"] = panel.name
    mark_processed(state, processed_items, new_items)
    save_state(state)
    move_sent_artifacts(panel, html_panel, image_panel, label)
    print("[push-telegram] done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
