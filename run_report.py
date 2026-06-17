#!/usr/bin/env python3
"""Shared batch/run health report for Daily Inbox.

The consumer digest, owner status page, and watchdog alerts must not each invent
their own numbers. This module builds one small JSON-compatible report from the
active batch plus runtime health sidecars.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from lib import PARKIO, ROOT, batch_id, batch_label, processed_batch_dir, today

MEDIA_SUMMARIES_PATH = ROOT / "media-summaries.json"
SCORING_HEALTH_PATH = ROOT / "scoring-health.json"
WEWE_AUTH_ALERT_PATH = PARKIO / "_inbox" / "wewe-auth-alert.json"


def report_path(batch: str | None = None) -> Path:
    return processed_batch_dir(batch) / "run-report.json"


def _short_error(text: str) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    if not value:
        return "未知错误"
    if "cookies-file:youtube-cookies.txt" in value or "Sign in to confirm" in value or "ERROR: [youtube]" in value:
        return "YouTube cookie/登录态可能失效"
    if "ReadTimeout" in value or "timed out" in value.lower():
        return "下载或转录超时"
    if "UNEXPECTED_EOF" in value or "urlopen error" in value or "SSL:" in value:
        return "网络/SSL 连接异常"
    if "skipped_too_long" in value:
        return "视频过长，已跳过"
    return value[:120]


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def media_status_rows_for_urls(urls: set[str] | None = None, date: str | None = None) -> list[dict[str, str]]:
    data = _load_json(MEDIA_SUMMARIES_PATH)
    if not isinstance(data, dict):
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for rec in data.values():
        if not isinstance(rec, dict):
            continue
        status = str(rec.get("status") or "")
        if status not in {"failed", "skipped_short", "skipped_too_long", "no_transcript"}:
            continue
        url = str(rec.get("url") or "")
        if urls is not None and url not in urls:
            continue
        if urls is None and date and str(rec.get("updated_at", ""))[:10] != date:
            continue
        key = url or f"{rec.get('source')}::{rec.get('title')}"
        if key in seen:
            continue
        seen.add(key)
        if status == "skipped_short":
            detail = "YouTube Shorts，按规则不进深度正文"
        elif status == "skipped_too_long":
            detail = "视频过长，已跳过"
        elif status == "no_transcript":
            detail = "没有可用字幕或转录"
        else:
            detail = _short_error(str(rec.get("error") or ""))
        rows.append(
            {
                "source": str(rec.get("source") or "未知来源"),
                "title": str(rec.get("title") or url or "未命名音视频"),
                "url": url,
                "status": status,
                "error": detail,
            }
        )
    rows.sort(key=lambda row: (row["source"], row["title"]))
    return rows


def media_failures_for_date(date: str) -> list[dict[str, str]]:
    return [row for row in media_status_rows_for_urls(None, date) if row.get("status") == "failed"]


def media_issues_for_batch(sources: list[dict[str, Any]], date: str) -> list[dict[str, str]]:
    urls: set[str] = set()
    for src in sources:
        for item in src.get("items", []):
            url = str(item.get("url") or "")
            if "youtube.com/" in url or "youtu.be/" in url or "douyin.com/video/" in url:
                urls.add(url)
    if not urls:
        return []
    return media_status_rows_for_urls(urls, date)


def scoring_problem_for_date(date: str) -> dict[str, Any] | None:
    data = _load_json(SCORING_HEALTH_PATH)
    if not isinstance(data, dict) or data.get("date") != date:
        return None
    failed = int(data.get("failed_batches", 0) or 0)
    status = str(data.get("status") or "unknown")
    if status == "ok" and failed == 0:
        return None
    return {
        "status": status,
        "failed_batches": failed,
        "total_batches": int(data.get("total_batches", 0) or 0),
        "message": f"打分服务异常：{failed} 个批次失败，status={status}",
    }


def wewe_auth_problem(date: str | None = None) -> dict[str, str] | None:
    data = _load_json(WEWE_AUTH_ALERT_PATH)
    if not isinstance(data, dict):
        return None
    if date and str(data.get("checked_at") or "")[:10] != date:
        return None
    status = data.get("status")
    if status == "invalid":
        return {
            "name": "公众号登录态",
            "status": "failed",
            "detail": "WeWe 读书账号失效；请扫码重新登录",
        }
    if status == "failed":
        return {
            "name": "公众号登录态",
            "status": "failed",
            "detail": f"WeWe 状态检测失败：{data.get('error', '未知错误')}",
        }
    return None


def source_problems(health: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows = []
    for row in health:
        status = row.get("status")
        if status not in {"failed", "stale"}:
            continue
        rows.append(
            {
                "name": str(row.get("name") or "未知来源"),
                "platform": str(row.get("platform") or ""),
                "status": str(status),
                "detail": _short_error(str(row.get("detail") or "")),
            }
        )
    return rows


def dependency_summary(media_failures: list[dict[str, str]], source_issues: list[dict[str, str]], date: str | None = None) -> list[dict[str, str]]:
    deps: list[dict[str, str]] = []
    wewe_issue = wewe_auth_problem(date)
    if wewe_issue:
        deps.append(wewe_issue)
    if media_failures:
        cookie_related = [row for row in media_failures if "cookie" in row.get("error", "").lower() or "登录态" in row.get("error", "")]
        detail = "YouTube cookie/登录态可能失效" if cookie_related else "存在音视频转录未完成"
        deps.append({"name": "音视频转录", "status": "failed", "detail": f"{len(media_failures)} 条异常；{detail}"})
    if any(row["platform"] == "twitter" for row in source_issues):
        deps.append({"name": "X 抓取", "status": "failed", "detail": "存在 X 来源抓取失败或上游冻结"})
    if any(row["platform"] == "wechat" for row in source_issues):
        deps.append({"name": "公众号 RSS", "status": "failed", "detail": "存在公众号来源抓取失败或上游冻结"})
    if any(row["platform"] == "douyin" for row in source_issues):
        deps.append({"name": "抖音抓取", "status": "failed", "detail": "存在抖音来源抓取失败或上游冻结"})
    return deps


def build_run_report(
    sources: list[dict[str, Any]],
    health: list[dict[str, Any]],
    date: str | None = None,
    batch: str | None = None,
) -> dict[str, Any]:
    date = date or today()
    batch = batch or batch_id()
    total = sum(len(src.get("items", [])) for src in sources)
    kept = sum(len(src.get("kept", [])) for src in sources)
    filtered = sum(len(src.get("filtered", [])) for src in sources)
    health_counts = Counter(str(row.get("status") or "unknown") for row in health)
    media_issues = media_issues_for_batch(sources, date) or media_status_rows_for_urls(None, date)
    media_failures = [row for row in media_issues if row.get("status") == "failed"]
    src_problems = source_problems(health)
    scoring = scoring_problem_for_date(date)
    deps = dependency_summary(media_failures, src_problems, date)
    direct_deps = [row for row in deps if row.get("name") == "公众号登录态"]
    problems: list[dict[str, Any]] = []
    problems.extend({"kind": "source", **row} for row in src_problems)
    problems.extend({"kind": "media_transcription", **row} for row in media_failures)
    problems.extend({"kind": "dependency", **row} for row in direct_deps)
    if scoring:
        problems.append({"kind": "scoring", **scoring})
    report = {
        "schema": 1,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "batch" if (os.environ.get("PARKIO_BATCH_ID") or os.environ.get("PARKIO_BATCH_DIR")) else "current_queue",
        "date": date,
        "batch_id": batch,
        "batch_label": batch_label(batch),
        "batch_dir": str(processed_batch_dir(batch)),
        "totals": {
            "source_files": len(sources),
            "items": total,
            "kept": kept,
            "filtered": filtered,
        },
        "health": {
            "counts": dict(health_counts),
            "healthy": sum(1 for row in health if row.get("status") in {"ok_new", "ok_no_new", "filtered_out"}),
            "new_today": health_counts.get("ok_new", 0),
            "needs_attention": len(src_problems) + len(media_failures) + len(direct_deps) + (1 if scoring else 0),
            "source_problems": src_problems,
            "media_failures": media_failures,
            "media_issues": media_issues,
            "dependencies": deps,
            "scoring": scoring,
        },
        "problems": problems,
    }
    return report


def write_run_report(report: dict[str, Any], batch: str | None = None) -> Path:
    path = report_path(batch or str(report.get("batch_id") or ""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_run_report(batch: str | None = None) -> dict[str, Any] | None:
    data = _load_json(report_path(batch))
    return data if isinstance(data, dict) else None


def latest_run_report(date: str | None = None) -> dict[str, Any] | None:
    date = date or today()
    label = date[2:] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date) else batch_label(date)
    candidates = sorted((processed_batch_dir().parent).glob(f"{label}*/run-report.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in candidates:
        data = _load_json(path)
        if isinstance(data, dict):
            return data
    return None


def problem_lines(report: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for row in report.get("health", {}).get("source_problems", []):
        lines.append(f"{row.get('name')}（{row.get('detail') or row.get('status')}）")
    for row in report.get("health", {}).get("media_failures", []):
        lines.append(f"{row.get('source')}：{row.get('title')}（转录未完成：{row.get('error')}）")
    for row in report.get("health", {}).get("dependencies", []):
        if row.get("name") != "公众号登录态":
            continue
        lines.append(f"{row.get('name')}（{row.get('detail') or row.get('status')}）")
    scoring = report.get("health", {}).get("scoring")
    if scoring:
        lines.append(str(scoring.get("message") or "打分服务异常"))
    return lines


def compact_digest_health_lines(report: dict[str, Any]) -> list[str]:
    health = report.get("health", {})
    source_problems = health.get("source_problems", [])
    media_failures = health.get("media_failures", [])
    deps = health.get("dependencies", [])
    lines = [
        "",
        "## 渠道概览",
        "",
        f"- 健康渠道 **{health.get('healthy', 0)}** · 今日有新增 **{health.get('new_today', 0)}** · 需关注 **{health.get('needs_attention', 0)}**",
    ]
    if source_problems:
        names = "、".join(str(row.get("name") or "") for row in source_problems[:6])
        more = f" 等 {len(source_problems)} 个" if len(source_problems) > 6 else ""
        lines.append(f"- ⚠ 来源异常：{names}{more}")
    if media_failures:
        sources = sorted({str(row.get("source") or "未知来源") for row in media_failures})
        lines.append(f"- ⚠ 音视频转录异常 **{len(media_failures)}** 条：{ '、'.join(sources[:5]) }")
    dep_failures = [row for row in deps if row.get("status") != "ok" and row.get("name") == "公众号登录态"]
    if dep_failures:
        details = "；".join(str(row.get("detail") or row.get("name") or "") for row in dep_failures[:3])
        lines.append(f"- ⚠ 依赖异常 **{len(dep_failures)}** 项：{details}")
    if not source_problems and not media_failures and not deps:
        lines.append("- ✅ 所有自动渠道今日抓取正常")
    return lines
