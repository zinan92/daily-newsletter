#!/usr/bin/env python3
"""Build the single reader-facing AI Daily Newsletter Markdown.

Brief, deep-read, and product radar remain separate intermediate artifacts under
processed/<YY-MM-DD>/ for debugging. The durable reader artifact is one Markdown
file under ~/park-io/006_ai daily newsletter/.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from lib import PROCESSED_DIR, SENT_DIR, batch_id, today


@dataclass(frozen=True)
class Artifact:
    key: str
    title: str
    md: Path


def run_date_from_batch(batch: str | None = None) -> str:
    batch = batch or batch_id()
    if re.fullmatch(r"\d{8,12}", batch):
        head = batch[:8]
        return f"{head[:4]}-{head[4:6]}-{head[6:8]}"
    current = today()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", current):
        return current
    return datetime.now().strftime("%Y-%m-%d")


def label_for_date(run_date: str) -> str:
    return datetime.strptime(run_date, "%Y-%m-%d").strftime("%y-%m-%d")


def product_artifacts(run_date: str) -> list[Artifact]:
    label = label_for_date(run_date)
    base = PROCESSED_DIR / label
    return [
        Artifact("brief", "快讯", base / f"000-{label}.md"),
        Artifact("deep", "深读", base / f"deep-{label}.md"),
        Artifact("product_radar", "产品雷达", base / f"product-radar-{label}.md"),
    ]


def daily_bundle_paths(run_date: str, sent_dir: Path = SENT_DIR) -> tuple[Path, Path, Path]:
    label = label_for_date(run_date)
    return sent_dir / f"{label}.md", sent_dir / f"{label}.html", sent_dir / f"{label}.png"


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _link(label: str, path: Path) -> str:
    return f"[{label}](<{path}>)"


def _line_count(markdown: str, pattern: str) -> int:
    return len(re.findall(pattern, markdown, flags=re.M))


def artifact_summary(artifact: Artifact) -> dict[str, object]:
    text = _read(artifact.md)
    exists = artifact.md.exists()
    if artifact.key == "brief":
        count = _line_count(text, r"^- \*\*")
        detail = f"{count} 条快讯信号" if exists else "未生成"
    elif artifact.key == "deep":
        count = _line_count(text, r"^###\s+")
        if exists and "今日没有达到深读标准" in text:
            count = 0
        detail = f"{count} 条深读候选" if exists else "未生成"
    else:
        count = _line_count(text, r"^###\s+\d+\.")
        detail = f"{count} 个可 build 产品方向" if exists else "未生成"
    return {
        "key": artifact.key,
        "title": artifact.title,
        "exists": exists,
        "detail": detail,
        "md": str(artifact.md),
        "html": "",
        "png": "",
    }


def product_radar_raw_path(run_date: str) -> Path:
    from lib import INBOX

    return INBOX / "raw" / run_date / "product-radar.json"


def product_radar_data_quality(run_date: str) -> list[str]:
    path = product_radar_raw_path(run_date)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    lines: list[str] = []
    for row in data.get("meta", []):
        source = row.get("source") or "unknown"
        fetched = row.get("fetched", 0)
        errors = row.get("errors") or []
        status = "OK" if fetched else "PARTIAL"
        detail = f"{source} {status}，抓到 {fetched} 条"
        if errors:
            detail += f"，错误 {len(errors)} 个"
        lines.append(detail)
    return lines


def run_report_lines(run_date: str) -> list[str]:
    try:
        from run_report import latest_run_report
    except Exception:
        return []
    report = latest_run_report(run_date)
    if not report:
        return []
    health = report.get("health") or {}
    lines = []
    for dep in health.get("dependencies") or []:
        lines.append(f"{dep.get('name')}：{dep.get('detail')}")
    source_problems = health.get("source_problems") or []
    media_failures = health.get("media_failures") or []
    if source_problems:
        lines.append(f"来源异常：{len(source_problems)} 个 source 需要关注")
    if media_failures:
        lines.append(f"音视频异常：{len(media_failures)} 条转录/下载异常")
    reader_quality = health.get("reader_quality") or {}
    if reader_quality:
        status = reader_quality.get("status")
        if status == "pass":
            lines.append("读者产物 QA：通过")
        elif status == "warn":
            lines.append(f"读者产物 QA：{reader_quality.get('warn_count', 0)} 个 warning")
        elif status == "fail":
            lines.append(f"读者产物 QA：{reader_quality.get('fail_count', 0)} 个 blocker")
    feishu = health.get("feishu") or {}
    if feishu:
        if feishu.get("status") == "sent":
            lines.append(f"飞书发送：已发送 {feishu.get('chunks', 0)} 段，{feishu.get('chars', 0)} 字")
        elif feishu.get("status"):
            lines.append(f"飞书发送：{feishu.get('status')}")
    return lines


MACHINE_COMMENT_RE = re.compile(r"\n?<!--\s*parkio-[\s\S]*?-->\s*", re.M)


def clean_reader_markdown(markdown: str) -> str:
    text = MACHINE_COMMENT_RE.sub("\n", markdown)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def remove_h1(markdown: str) -> str:
    text = clean_reader_markdown(markdown)
    lines = text.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
        while lines and not lines[0].strip():
            lines = lines[1:]
    return "\n".join(lines).strip()


def product_radar_section(markdown: str) -> str:
    body = remove_h1(markdown)
    if not body:
        return ""
    body = re.sub(r"^##\s+(Top\s+.+)$", r"### \1", body, flags=re.M)
    body = re.sub(r"^##\s+(No New Build Choices Today)\s*$", r"### \1", body, flags=re.M)
    return "## 产品雷达\n\n" + body.strip()


def render_markdown(run_date: str, sent_dir: Path = SENT_DIR, extra_warnings: list[str] | None = None) -> str:
    artifacts = product_artifacts(run_date)
    summaries = [artifact_summary(a) for a in artifacts]
    by_key = {artifact.key: artifact for artifact in artifacts}
    lines = [f"# AI Daily Newsletter — {run_date}", ""]

    brief = remove_h1(_read(by_key["brief"].md))
    lines.append(brief or "## 快讯\n\n今日没有生成快讯。")

    deep = remove_h1(_read(by_key["deep"].md))
    lines.extend(["", deep or "## 深读\n\n今日没有达到深读标准的内容。"])

    radar = product_radar_section(_read(by_key["product_radar"].md))
    lines.extend(["", radar or "## 产品雷达\n\n### Top Three Products to Build Today\n\n今天产品雷达暂不可用。"])

    text = "\n".join(part.strip() for part in lines if part.strip()).strip() + "\n"
    # Preserve summary calculation for run-report/status consumers.
    _ = summaries, sent_dir, extra_warnings
    return text


def build_daily_bundle(
    run_date: str | None = None,
    *,
    sent_dir: Path = SENT_DIR,
    with_png: bool = True,
    extra_warnings: list[str] | None = None,
) -> dict[str, object]:
    run_date = run_date or run_date_from_batch()
    sent_dir.mkdir(parents=True, exist_ok=True)
    markdown = render_markdown(run_date, sent_dir, extra_warnings)
    md_path, html_path, png_path = daily_bundle_paths(run_date, sent_dir)
    md_path.write_text(markdown, encoding="utf-8")
    return {
        "date": run_date,
        "markdown": str(md_path),
        "html": "",
        "png": "",
        "products": [artifact_summary(a) for a in product_artifacts(run_date)],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the single AI Daily Newsletter Markdown artifact.")
    parser.add_argument("--date", default=run_date_from_batch())
    parser.add_argument("--no-png", action="store_true", help="Legacy no-op; final reader output is Markdown-only.")
    parser.add_argument("--warning", action="append", default=[])
    args = parser.parse_args(argv)
    result = build_daily_bundle(args.date, with_png=not args.no_png, extra_warnings=args.warning)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
