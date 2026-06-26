#!/usr/bin/env python3
"""Final reader-surface QA for Daily Inbox artifacts.

This is intentionally narrower than the legacy digest quality gates: it checks
the exact Markdown products that readers will see, plus the Feishu body derived
from them. It does not rewrite content and it does not provide a fallback
renderer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from lib import PROCESSED_DIR, SENT_DIR


MACHINE_COMMENT_RE = re.compile(r"<!--\s*parkio-[\s\S]*?-->", re.M)
LOCAL_PATH_RE = re.compile(r"/Users/[^\s>)]+")
RAW_TRANSCRIPT_RE = re.compile(r"\bTranscript\b|转录原文|原始转录", re.I)
FILLER_RE = re.compile(r"(干杯|就是这样|我知道|是的)[。.\s，,、]*(?:\1[。.\s，,、]*){2,}")
PRODUCT_HEADING_RE = re.compile(r"^###\s+\d+\.", re.M)
TOP_N_RE = re.compile(r"Top\s+(\d+)\s+Products?", re.I)


def date_label(run_date: str) -> str:
    dt = datetime.strptime(run_date, "%Y-%m-%d")
    return dt.strftime("%y-%m-%d")


def processed_dir_for_date(run_date: str) -> Path:
    return PROCESSED_DIR / date_label(run_date)


def receipt_dir() -> Path:
    return PROCESSED_DIR / "receipts" / "reader-quality"


def output_path(run_date: str) -> Path:
    return processed_dir_for_date(run_date) / "reader-quality.json"


def reader_artifacts(run_date: str, sent_dir: Path = SENT_DIR) -> dict[str, Path]:
    label = date_label(run_date)
    return {
        "daily": sent_dir / f"daily-{label}.md",
        "brief": sent_dir / f"{label}.md",
        "deep": sent_dir / f"deep-{label}.md",
        "product_radar": sent_dir / f"product-radar-{label}.md",
    }


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _issue(severity: str, artifact: str, code: str, message: str, path: Path | None = None) -> dict[str, str]:
    row = {
        "severity": severity,
        "artifact": artifact,
        "code": code,
        "message": message,
    }
    if path:
        row["path"] = str(path)
    return row


def check_text(name: str, path: Path, text: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if MACHINE_COMMENT_RE.search(text):
        issues.append(_issue("fail", name, "machine_comment", "reader Markdown contains parkio machine markers", path))
    if name != "daily" and LOCAL_PATH_RE.search(text):
        issues.append(_issue("fail", name, "local_path", "reader Markdown contains local /Users path", path))
    if RAW_TRANSCRIPT_RE.search(text):
        issues.append(_issue("fail", name, "raw_transcript", "reader Markdown exposes raw transcript text", path))
    if FILLER_RE.search(text):
        issues.append(_issue("fail", name, "repeated_filler", "reader Markdown contains repeated transcript filler", path))
    return issues


def check_required_sections(name: str, path: Path, text: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if name == "brief":
        for heading in ("## 快讯", "### 底层工具", "### 工作流", "### 内容"):
            if heading not in text:
                issues.append(_issue("fail", name, "missing_section", f"brief is missing required heading: {heading}", path))
    elif name == "deep":
        if "## 深读" not in text:
            issues.append(_issue("fail", name, "missing_section", "deep product is missing ## 深读", path))
    elif name == "product_radar":
        if "## 数据质量" not in text:
            issues.append(_issue("warn", name, "missing_data_quality", "product radar is missing data quality section", path))
        headings = PRODUCT_HEADING_RE.findall(text)
        match = TOP_N_RE.search(text)
        if match and headings:
            advertised = int(match.group(1))
            if advertised != len(headings):
                issues.append(
                    _issue(
                        "warn",
                        name,
                        "top_n_mismatch",
                        f"product radar advertises Top {advertised} but renders {len(headings)} choices",
                        path,
                    )
                )
    elif name == "daily":
        for heading in ("## 今日包", "## Source Health"):
            if heading not in text:
                issues.append(_issue("warn", name, "missing_section", f"daily bundle is missing heading: {heading}", path))
    return issues


def check_artifacts(run_date: str, sent_dir: Path = SENT_DIR) -> dict[str, Any]:
    artifacts = reader_artifacts(run_date, sent_dir)
    issues: list[dict[str, str]] = []
    artifact_rows: dict[str, dict[str, Any]] = {}
    for name, path in artifacts.items():
        required = name in {"daily", "brief", "product_radar"}
        if not path.exists():
            if required:
                issues.append(_issue("fail", name, "missing_artifact", f"required reader artifact missing: {path}", path))
            artifact_rows[name] = {"exists": False, "path": str(path)}
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        artifact_rows[name] = {
            "exists": True,
            "path": str(path),
            "chars": len(text),
            "sha256": _sha256(text),
        }
        issues.extend(check_text(name, path, text))
        issues.extend(check_required_sections(name, path, text))

    fail_count = sum(1 for row in issues if row.get("severity") == "fail")
    warn_count = sum(1 for row in issues if row.get("severity") == "warn")
    status = "fail" if fail_count else ("warn" if warn_count else "pass")
    return {
        "schema": 1,
        "date": run_date,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "fail_count": fail_count,
        "warn_count": warn_count,
        "issues": issues,
        "artifacts": artifact_rows,
    }


def write_quality_report(report: dict[str, Any], run_date: str) -> Path:
    path = output_path(run_date)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_quality_report(run_date: str) -> dict[str, Any] | None:
    path = output_path(run_date)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, help="Run date in YYYY-MM-DD")
    parser.add_argument("--sent-dir", type=Path, default=SENT_DIR)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)

    report = check_artifacts(args.date, args.sent_dir)
    if not args.no_write:
        write_quality_report(report, args.date)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
