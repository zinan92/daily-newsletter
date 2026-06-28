#!/usr/bin/env python3
"""Poll the Feishu "好文收藏" chat and archive explicit links into Park-IO."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ingestion.collection_index import existing_collection_path_for_url, rebuild_collection_index
from lib import LIBRARY_DIR, collection_item_filename, collection_source_code, load_state, log, save_state, today

DEFAULT_CHAT_ID = "oc_981fc0b83b25e008df425384aa7c7910"
DEFAULT_CHAT_NAME = "好文收藏"
STATE_KEY = "feishu-favorites"
URL_RE = re.compile(r"https?://[^\s<>)\]]+")
TRAILING_URL_PUNCT = ".,;:!?，。；：！？)]）】"
X_STATUS_RE = re.compile(r"https?://(?:x|twitter)\.com/([^/\s]+)/status/(\d+)", re.I)
X_ITEMS_PATH = REPO_ROOT / "x-saved-items.json"


def clean_url(url: str) -> str:
    return url.rstrip(TRAILING_URL_PUNCT)


def extract_urls(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in URL_RE.findall(text or ""):
        url = clean_url(raw)
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


def run_lark_messages(chat_id: str, page_size: int) -> list[dict]:
    cli = shutil.which("lark-cli")
    if not cli:
        raise RuntimeError("lark-cli not found in PATH")
    cmd = [
        cli,
        "im",
        "+chat-messages-list",
        "--as",
        "user",
        "--chat-id",
        chat_id,
        "--page-size",
        str(page_size),
        "--sort",
        "desc",
        "--format",
        "json",
    ]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip())
    payload = json.loads(proc.stdout)
    if not payload.get("ok"):
        raise RuntimeError(json.dumps(payload, ensure_ascii=False))
    return list(payload.get("data", {}).get("messages", []))


def load_x_items() -> dict:
    if not X_ITEMS_PATH.exists():
        return {}
    try:
        data = json.loads(X_ITEMS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def title_from_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.replace("www.", "")
    path = parsed.path.strip("/")
    if not path:
        return host or "收藏链接"
    tail = path.split("/")[-1]
    return f"{host}-{tail}"[:80]


def x_metadata(url: str, x_items: dict) -> dict:
    match = X_STATUS_RE.match(url)
    if not match:
        return {}
    tweet_id = match.group(2)
    item = x_items.get(tweet_id) or {}
    return item if isinstance(item, dict) else {}


def source_code_for_url(url: str) -> str:
    if X_STATUS_RE.match(url):
        return "X"
    host = urlparse(url).netloc.lower()
    if "mp.weixin.qq.com" in host:
        return "WX"
    if "feishu.cn" in host or "larksuite.com" in host:
        return "Feishu"
    if "youtube.com" in host or "youtu.be" in host:
        return "YouTube"
    if "github.com" in host:
        return "GitHub"
    return collection_source_code({"platform": "web", "name": host}, {"url": url}, url)


def item_for_url(url: str, x_items: dict) -> dict:
    x_item = x_metadata(url, x_items)
    if x_item:
        title = x_item.get("articleTitle") or x_item.get("text") or title_from_url(url)
        body = str(x_item.get("text") or "").strip()
        has_body = bool(body and not re.fullmatch(r"https?://\S+", body))
        return {
            "source": "X",
            "source_platform": "x",
            "title": title,
            "author": x_item.get("author") or "",
            "handle": x_item.get("handle") or "",
            "tweet_created_at": x_item.get("tweet_created_at") or "",
            "body": body,
            "status": "archived" if has_body else "needs_fetch",
            "extra_urls": x_item.get("urls") or [],
            "metrics": x_item.get("metrics") or {},
        }
    return {
        "source": source_code_for_url(url),
        "source_platform": source_code_for_url(url).lower(),
        "title": title_from_url(url),
        "author": "",
        "handle": "",
        "tweet_created_at": "",
        "body": "",
        "status": "needs_fetch",
        "extra_urls": [],
        "metrics": {},
    }


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for idx in range(2, 100):
        candidate = path.with_name(f"{stem}-{idx}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"cannot create unique path for {path}")


def message_date(message: dict) -> str:
    value = str(message.get("create_time") or "")
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return today()


def render_markdown(url: str, item: dict, message: dict, chat_id: str, chat_name: str) -> str:
    title = str(item.get("title") or title_from_url(url)).replace("\n", " ").strip()
    author = str(item.get("author") or "").replace("\n", " ").strip()
    handle = str(item.get("handle") or "").replace("\n", " ").strip()
    metrics = item.get("metrics") if isinstance(item.get("metrics"), dict) else {}
    metric_text = " · ".join(
        f"{key} {value}" for key, value in metrics.items() if value not in ("", None)
    )
    lines = [
        "---",
        f"id: {url}",
        f"source: {item.get('source') or source_code_for_url(url)}",
        f"source_platform: {item.get('source_platform') or ''}",
        f"source_url: {url}",
        f"source_chat: {chat_name}",
        f"source_chat_id: {chat_id}",
        f"source_message_id: {message.get('message_id', '')}",
        f"source_message_link: {message.get('message_app_link', '')}",
        f"author: {author}",
        f"handle: {handle}",
        f"tweet_created_at: {item.get('tweet_created_at') or ''}",
        f"captured_at: {message.get('create_time') or datetime.now().isoformat(timespec='seconds')}",
        f"status: {item.get('status') or 'needs_fetch'}",
        "tags: ",
        "---",
        "",
        f"# {title}",
        "",
        f"> 从飞书群 `{chat_name}` 捕获。",
        "",
        f"原文链接：[{url}]({url})",
    ]
    if author or handle:
        handle_text = f" (@{handle})" if handle else ""
        lines.append(f"作者：{author}{handle_text}")
    if metric_text:
        lines.append(f"公开互动：{metric_text}")
    extra_urls = [str(u) for u in item.get("extra_urls") or [] if str(u) != url]
    if extra_urls:
        lines.extend(["", "## 相关链接", ""])
        for extra in extra_urls:
            lines.append(f"- {extra}")
    body = str(item.get("body") or "").strip()
    if body:
        lines.extend(["", "## 正文缓存", "", body])
    if item.get("status") == "needs_fetch":
        lines.extend(["", "## 待补", "", "- [ ] 抓取或补全正文。"])
    lines.append("")
    return "\n".join(lines)


def archive_url(url: str, message: dict, chat_id: str, chat_name: str, x_items: dict, dry_run: bool) -> str:
    existing = existing_collection_path_for_url(url)
    if existing:
        return f"exists:{existing.name}"
    item = item_for_url(url, x_items)
    identity = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    filename = collection_item_filename(
        message_date(message),
        source_code_for_url(url),
        str(item.get("title") or title_from_url(url)),
        identity,
    )
    path = unique_path(LIBRARY_DIR / filename)
    if dry_run:
        return f"would_create:{path.name}"
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(url, item, message, chat_id, chat_name), encoding="utf-8")
    return f"created:{path.name}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chat-id", default=DEFAULT_CHAT_ID)
    parser.add_argument("--chat-name", default=DEFAULT_CHAT_NAME)
    parser.add_argument("--page-size", type=int, default=50)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    messages = run_lark_messages(args.chat_id, args.page_size)
    state = load_state()
    current = dict(state.get(STATE_KEY) or {})
    seen_messages = set(current.get("seen_message_ids") or [])
    seen_urls = set(current.get("seen_urls") or [])
    x_items = load_x_items()

    created = 0
    skipped = 0
    results: list[str] = []

    for message in sorted(messages, key=lambda row: str(row.get("create_time") or "")):
        message_id = str(message.get("message_id") or "")
        if message_id in seen_messages:
            skipped += 1
            continue
        urls = extract_urls(str(message.get("content") or ""))
        if not urls:
            seen_messages.add(message_id)
            continue
        for url in urls:
            if url in seen_urls:
                results.append(f"duplicate:{url}")
                continue
            result = archive_url(url, message, args.chat_id, args.chat_name, x_items, args.dry_run)
            results.append(f"{result}:{url}")
            if result.startswith("created:"):
                created += 1
            seen_urls.add(url)
        seen_messages.add(message_id)

    if not args.dry_run:
        current.update(
            {
                "chat_id": args.chat_id,
                "chat_name": args.chat_name,
                "last_fetch": datetime.now().isoformat(timespec="seconds"),
                "seen_message_ids": sorted(seen_messages)[-1000:],
                "seen_urls": sorted(seen_urls)[-2000:],
            }
        )
        state[STATE_KEY] = current
        save_state(state)
        rebuild_collection_index()

    for line in results:
        log("feishu-favorites", line)
    log("feishu-favorites", f"DONE — created {created}, skipped {skipped}, dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
