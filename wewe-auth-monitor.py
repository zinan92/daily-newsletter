#!/usr/bin/env python3
"""Monitor WeWe RSS account login state and prepare a QR login alert.

This is a local owner-facing guard. It does not fetch articles itself; it only
checks whether the WeWe RSS bridge account is still valid. When invalid, it
writes a JSON sidecar plus a QR image that status.html can display.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from lib import PARKIO, log

BASE_URL = os.environ.get("PARKIO_WEWE_URL", "http://localhost:4000").rstrip("/")
AUTH_CODE = os.environ.get("PARKIO_WEWE_AUTH_CODE", "parkio")
ALERT_PATH = PARKIO / "_inbox" / "wewe-auth-alert.json"
QR_PATH = PARKIO / "_inbox" / "wewe-auth-qr.png"

STATUS_LABELS = {
    0: "失效",
    1: "启用",
    2: "禁用",
}


def _headers() -> dict[str, str]:
    return {
        "Authorization": AUTH_CODE,
        "Content-Type": "application/json",
        "User-Agent": "parkio-wewe-auth-monitor/1",
    }


def _trpc_get(name: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    query = urllib.parse.urlencode({"input": json.dumps({"json": payload or {}}, ensure_ascii=False)})
    req = urllib.request.Request(f"{BASE_URL}/trpc/{name}?{query}", headers=_headers())
    with urllib.request.urlopen(req, timeout=12) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _trpc_post(name: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = json.dumps({"json": payload or {}}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}/trpc/{name}", data=body, headers=_headers(), method="POST")
    with urllib.request.urlopen(req, timeout=12) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _unwrap_result(payload: dict[str, Any]) -> Any:
    data = payload.get("result", {}).get("data", {})
    if isinstance(data, dict) and "json" in data:
        return data.get("json")
    return data


def _write_qr(scan_url: str) -> bool:
    try:
        import qrcode
    except Exception as exc:
        log("wewe-auth-monitor", f"qrcode unavailable: {type(exc).__name__}: {exc}")
        return False
    QR_PATH.parent.mkdir(parents=True, exist_ok=True)
    img = qrcode.make(scan_url)
    img.save(QR_PATH)
    return True


def _account_rows(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, dict):
        items = raw.get("items") or raw.get("list") or []
    elif isinstance(raw, list):
        items = raw
    else:
        items = []
    rows: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        status = item.get("status")
        try:
            status_int = int(status)
        except (TypeError, ValueError):
            status_int = -1
        rows.append(
            {
                "id": str(item.get("id") or ""),
                "name": str(item.get("name") or item.get("nickname") or "未知账号"),
                "status": status_int,
                "status_label": STATUS_LABELS.get(status_int, f"未知({status})"),
                "updatedAt": str(item.get("updatedAt") or item.get("updated_at") or ""),
            }
        )
    return rows


def write_alert(payload: dict[str, Any]) -> None:
    ALERT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ALERT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    checked_at = datetime.now().isoformat(timespec="seconds")
    try:
        account_payload = _trpc_get("account.list")
        accounts = _account_rows(_unwrap_result(account_payload))
        invalid = [row for row in accounts if row["status"] == 0]
        disabled = [row for row in accounts if row["status"] == 2]
        if invalid:
            login_payload = _trpc_post("platform.createLoginUrl")
            login = _unwrap_result(login_payload) or {}
            scan_url = str(login.get("scanUrl") or "")
            qr_written = _write_qr(scan_url) if scan_url else False
            payload = {
                "checked_at": checked_at,
                "base_url": BASE_URL,
                "status": "invalid",
                "accounts": accounts,
                "invalid_accounts": invalid,
                "disabled_accounts": disabled,
                "login": {
                    "uuid": str(login.get("uuid") or ""),
                    "scanUrl": scan_url,
                    "qr_path": str(QR_PATH) if qr_written else "",
                    "expires_in_seconds": 60,
                    "generated_at": checked_at,
                },
            }
            write_alert(payload)
            log("wewe-auth-monitor", f"INVALID — {', '.join(row['name'] for row in invalid)}")
            return 0
        payload = {
            "checked_at": checked_at,
            "base_url": BASE_URL,
            "status": "ok",
            "accounts": accounts,
            "invalid_accounts": [],
            "disabled_accounts": disabled,
            "login": {},
        }
        write_alert(payload)
        log("wewe-auth-monitor", f"OK — {len(accounts)} account(s)")
        return 0
    except Exception as exc:
        detail = f"{type(exc).__name__}: {exc}"
        payload = {
            "checked_at": checked_at,
            "base_url": BASE_URL,
            "status": "failed",
            "accounts": [],
            "invalid_accounts": [],
            "login": {},
            "error": detail,
        }
        write_alert(payload)
        log("wewe-auth-monitor", f"FAILED — {detail}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
