#!/usr/bin/env python3
"""Send the daily Park-IO newsletter bundle to a Feishu bot webhook."""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
import re


PARKIO = Path.home() / "park-io"
DEFAULT_CONFIG = PARKIO / ".system" / "content-ops" / "secrets" / "feishu-digest.env"
SENT_DIR = PARKIO / "_inbox" / "sent"
RECEIPT_DIR = PARKIO / "_inbox" / "processed" / "receipts" / "feishu"
MAX_TEXT_CHARS = 3500
MACHINE_COMMENT_RE = re.compile(r"\n?<!--\s*parkio-[\s\S]*?-->", re.M)
LOCAL_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(<(/Users/[^>]+)>\)")
HTTP_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")


class FeishuPushError(RuntimeError):
    pass


def default_run_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def date_label(run_date: str) -> str:
    dt = datetime.strptime(run_date, "%Y-%m-%d")
    return dt.strftime("%y-%m-%d")


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        raise FeishuPushError(f"Feishu config missing: {path}")
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def signed_payload(webhook_secret: str, text: str) -> dict:
    timestamp = str(int(time.time()))
    string_to_sign = f"{timestamp}\n{webhook_secret}".encode("utf-8")
    sign = base64.b64encode(hmac.new(string_to_sign, b"", hashlib.sha256).digest()).decode("utf-8")
    return {
        "timestamp": timestamp,
        "sign": sign,
        "msg_type": "text",
        "content": {"text": text},
    }


def post_text(webhook_url: str, webhook_secret: str, text: str) -> dict:
    body = json.dumps(signed_payload(webhook_secret, text), ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        raise FeishuPushError(f"Feishu request failed: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise FeishuPushError(f"Feishu returned non-JSON response: {raw[:200]}") from exc
    if data.get("code") not in (0, None):
        raise FeishuPushError(f"Feishu returned error: {data}")
    return data


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def receipt_path(run_date: str, sent_at: str | None = None) -> Path:
    safe_ts = (sent_at or datetime.now().isoformat(timespec="seconds")).replace(":", "").replace("-", "").replace("T", "-")
    return RECEIPT_DIR / f"{run_date}-{safe_ts}.json"


def write_receipt(receipt: dict) -> Path:
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    path = receipt_path(str(receipt.get("date") or default_run_date()), str(receipt.get("sent_at") or ""))
    receipt["path"] = str(path)
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def update_run_report_feishu(receipt: dict) -> None:
    try:
        from run_report import latest_run_report, report_path
    except Exception:
        return
    report = latest_run_report(str(receipt.get("date") or ""))
    if not isinstance(report, dict):
        return
    report.setdefault("health", {})["feishu"] = receipt
    report.setdefault("funnel", {})["feishu"] = receipt
    path = report_path(str(report.get("batch_id") or ""))
    try:
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError:
        return


def chunk_text(text: str, limit: int = MAX_TEXT_CHARS) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in text.splitlines():
        add_len = len(line) + 1
        if current and current_len + add_len > limit:
            chunks.append("\n".join(current).strip())
            current = []
            current_len = 0
        current.append(line)
        current_len += add_len
    if current:
        chunks.append("\n".join(current).strip())
    return chunks


def artifact_path(run_date: str) -> Path:
    return SENT_DIR / f"daily-{date_label(run_date)}.md"


def artifact_paths(run_date: str) -> dict[str, Path]:
    label = date_label(run_date)
    return {
        "daily": SENT_DIR / f"daily-{label}.md",
        "brief": SENT_DIR / f"{label}.md",
        "deep": SENT_DIR / f"deep-{label}.md",
        "radar": SENT_DIR / f"product-radar-{label}.md",
    }


def readable_markdown(markdown: str) -> str:
    text = MACHINE_COMMENT_RE.sub("", markdown)
    text = LOCAL_MD_LINK_RE.sub(r"\1", text)
    text = HTTP_MD_LINK_RE.sub(r"\1 \2", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def read_artifact(path: Path, *, required: bool = True) -> str:
    if not path.exists():
        if required:
            raise FeishuPushError(f"Required artifact not found: {path}")
        return ""
    return readable_markdown(path.read_text(encoding="utf-8"))


def message_text(run_date: str, markdown_path: Path | None = None) -> str:
    paths = artifact_paths(run_date)
    daily = read_artifact(markdown_path or paths["daily"])
    brief = read_artifact(paths["brief"])
    deep = read_artifact(paths["deep"], required=False)
    radar = read_artifact(paths["radar"], required=False)
    sections = [
        f"Park-IO Daily Newsletter — {run_date}",
        "",
        "这条飞书消息包含完整正文；不需要打开本地 Markdown 文件。",
        "",
        daily,
        "",
        "====================",
        "快讯正文",
        "====================",
        brief,
    ]
    if deep:
        sections.extend(
            [
                "",
                "====================",
                "深读正文",
                "====================",
                deep,
            ]
        )
    if radar:
        sections.extend(
            [
                "",
                "====================",
                "产品雷达正文",
                "====================",
                radar,
            ]
        )
    return "\n".join(
        section.strip()
        for section in sections
        if section.strip()
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=default_run_date(), help="Run date in YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Path to Feishu webhook env file.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_env(args.config)
    webhook_url = config.get("FEISHU_WEBHOOK_URL", "")
    webhook_secret = config.get("FEISHU_WEBHOOK_SECRET", "")
    if not webhook_url or not webhook_secret:
        raise FeishuPushError(f"Missing FEISHU_WEBHOOK_URL or FEISHU_WEBHOOK_SECRET in {args.config}")

    path = artifact_path(args.date)
    if not path.exists():
        raise FeishuPushError(f"Daily bundle not found: {path}")

    try:
        from reader_quality import check_artifacts, write_quality_report

        quality = check_artifacts(args.date, SENT_DIR)
        write_quality_report(quality, args.date)
        if quality.get("status") == "fail":
            raise FeishuPushError(f"Reader quality failed: {quality.get('issues', [])}")
    except FeishuPushError:
        raise

    text = message_text(args.date, path)
    if "/Users/" in text or "parkio-" in text or "Transcript" in text:
        raise FeishuPushError("Feishu body still contains local path, machine marker, or raw Transcript text")
    chunks = chunk_text(text)
    total = len(chunks)
    sent_at = datetime.now().isoformat(timespec="seconds")
    receipt = {
        "schema": 1,
        "date": args.date,
        "sent_at": sent_at,
        "status": "started",
        "artifact": str(path),
        "artifact_sha256": sha256_text(path.read_text(encoding="utf-8")),
        "text_sha256": sha256_text(text),
        "chars": len(text),
        "chunks": total,
        "messages": [],
    }
    try:
        for idx, chunk in enumerate(chunks, 1):
            prefix = f"[{idx}/{total}]\n" if total > 1 else ""
            body = prefix + chunk
            response = post_text(webhook_url, webhook_secret, body)
            receipt["messages"].append(
                {
                    "index": idx,
                    "chars": len(body),
                    "sha256": sha256_text(body),
                    "response": response,
                }
            )
    except Exception as exc:
        receipt["status"] = "failed"
        receipt["error"] = f"{type(exc).__name__}: {exc}"
        written = write_receipt(receipt)
        update_run_report_feishu(receipt)
        print(f"[send-feishu-digest] failed; receipt={written}")
        raise
    receipt["status"] = "sent"
    written = write_receipt(receipt)
    update_run_report_feishu(receipt)
    print(f"[send-feishu-digest] sent {total} message(s) for {args.date}: {path}; receipt={written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
