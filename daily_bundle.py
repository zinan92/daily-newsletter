#!/usr/bin/env python3
"""Build the Daily Newsletter umbrella artifact.

The umbrella does not rewrite reader products. It links the three independent
daily products and records degraded status when one product is missing.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from lib import SENT_DIR, batch_id, today


@dataclass(frozen=True)
class Artifact:
    key: str
    title: str
    md: Path
    html: Path
    png: Path


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


def product_artifacts(run_date: str, sent_dir: Path = SENT_DIR) -> list[Artifact]:
    label = label_for_date(run_date)
    return [
        Artifact("brief", "快讯", sent_dir / f"{label}.md", sent_dir / f"{label}.html", sent_dir / f"{label}.png"),
        Artifact("deep", "深读", sent_dir / f"deep-{label}.md", sent_dir / f"deep-{label}.html", sent_dir / f"deep-{label}.png"),
        Artifact(
            "product_radar",
            "产品雷达",
            sent_dir / f"product-radar-{label}.md",
            sent_dir / f"product-radar-{label}.html",
            sent_dir / f"product-radar-{label}.png",
        ),
    ]


def daily_bundle_paths(run_date: str, sent_dir: Path = SENT_DIR) -> tuple[Path, Path, Path]:
    label = label_for_date(run_date)
    return sent_dir / f"daily-{label}.md", sent_dir / f"daily-{label}.html", sent_dir / f"daily-{label}.png"


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
        count = _line_count(text, r"^- \*\*")
        detail = f"{count} 条产品/需求/收入信号" if exists else "未生成"
    return {
        "key": artifact.key,
        "title": artifact.title,
        "exists": exists,
        "detail": detail,
        "md": str(artifact.md),
        "html": str(artifact.html) if artifact.html.exists() else "",
        "png": str(artifact.png) if artifact.png.exists() else "",
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
    return lines


def render_markdown(run_date: str, sent_dir: Path = SENT_DIR, extra_warnings: list[str] | None = None) -> str:
    artifacts = product_artifacts(run_date, sent_dir)
    summaries = [artifact_summary(a) for a in artifacts]
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    warnings = [w for w in (extra_warnings or []) if w]
    warnings.extend(run_report_lines(run_date))

    lines = [
        f"# Daily Newsletter — {run_date}",
        "",
        "## 今日包",
        "",
    ]
    for artifact, summary in zip(artifacts, summaries, strict=True):
        if summary["exists"]:
            links = [_link("Markdown", artifact.md)]
            if artifact.html.exists():
                links.append(_link("HTML", artifact.html))
            if artifact.png.exists():
                links.append(_link("PNG", artifact.png))
            lines.append(f"- **{artifact.title}**：{summary['detail']}。{' · '.join(links)}")
        else:
            lines.append(f"- **{artifact.title}**：未生成。")

    lines.extend(["", "## 产品关系", ""])
    lines.append("- **快讯** 是默认每日信息雷达，覆盖当天所有有用信号。")
    lines.append("- **深读** 是从快讯信号升级出来的文章级理解，不硬凑。")
    lines.append("- **产品雷达** 独立观察新产品、真实收入和用户痛点，服务“接下来可以做什么”。")

    radar_quality = product_radar_data_quality(run_date)
    if radar_quality:
        lines.extend(["", "## 产品雷达数据质量", ""])
        lines.extend(f"- {line}" for line in radar_quality)

    lines.extend(["", "## Source Health", ""])
    if warnings:
        lines.extend(f"- {line}" for line in warnings)
    else:
        lines.append("- 没有需要阻塞今日推送的异常。")
    lines.append("- WeChat / YouTube / 单个产品雷达源异常只进入健康提示，不阻塞每日 bundle 生成。")

    lines.extend(["", f"_生成时间：{generated}_", ""])
    return "\n".join(lines)


def write_html(markdown: str, html_path: Path, run_date: str) -> None:
    try:
        from aggregation.digest.summarize import render_html_from_markdown

        html_text = render_html_from_markdown(markdown, run_date, [], html_path.parent)
    except Exception:
        import html

        body = "\n".join(f"<p>{html.escape(line)}</p>" for line in markdown.splitlines())
        html_text = f"<!doctype html><meta charset='utf-8'><body>{body}</body>"
    html_path.write_text(html_text, encoding="utf-8")


def render_png(html_path: Path, png_path: Path) -> bool:
    try:
        from aggregation.digest.html_to_long_image import CHROME, trim_bottom_whitespace

        if not CHROME.exists():
            return False
        width = 1200
        height = 4000
        file_url = "file://" + urllib.parse.quote(str(html_path.resolve()))
        png_path.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(2):
            with tempfile.TemporaryDirectory(prefix="parkio-daily-bundle-chrome-") as user_data:
                try:
                    result = subprocess.run(
                        [
                            str(CHROME),
                            "--headless=new",
                            "--hide-scrollbars",
                            "--disable-gpu",
                            "--disable-dev-shm-usage",
                            "--no-first-run",
                            "--no-default-browser-check",
                            f"--user-data-dir={user_data}",
                            f"--window-size={width},{height}",
                            f"--screenshot={png_path}",
                            file_url,
                        ],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    if result.returncode == 0 and png_path.exists():
                        trim_bottom_whitespace(png_path)
                        return True
                except subprocess.TimeoutExpired:
                    if png_path.exists() and png_path.stat().st_size > 0:
                        return True
                if attempt == 0:
                    time.sleep(2)
    except Exception:
        return False
    return False


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
    write_html(markdown, html_path, run_date)
    png_ok = render_png(html_path, png_path) if with_png else False
    return {
        "date": run_date,
        "markdown": str(md_path),
        "html": str(html_path),
        "png": str(png_path) if png_ok else "",
        "products": [artifact_summary(a) for a in product_artifacts(run_date, sent_dir)],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the Daily Newsletter umbrella artifact.")
    parser.add_argument("--date", default=run_date_from_batch())
    parser.add_argument("--no-png", action="store_true")
    parser.add_argument("--warning", action="append", default=[])
    args = parser.parse_args(argv)
    result = build_daily_bundle(args.date, with_png=not args.no_png, extra_warnings=args.warning)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
