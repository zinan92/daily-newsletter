#!/usr/bin/env python3
"""Render a reproducible public verification GIF for the README.

The GIF is generated from real command output, then sanitized so local machine
paths are not published. It does not run the production newsletter or send any
external delivery.
"""
from __future__ import annotations

import argparse
import subprocess
import textwrap
import time
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GIF = ROOT / "examples" / "daily-newsletter-demo.gif"
DEFAULT_TRANSCRIPT = ROOT / "examples" / "daily-newsletter-demo-transcript.txt"

VERIFY_COMMANDS: list[tuple[str, list[str]]] = [
    ("Install-free public verification", ["python3", "-m", "pytest", "-q"]),
    ("Task graph contract", ["python3", "scripts/task_graph_validate.py"]),
    ("Workflow graph contract", ["python3", "scripts/workflow_graph_validate.py"]),
    ("Dry-run command waves", ["python3", "scripts/workflow_graph_dry_run.py"]),
    ("n8n projection drift check", ["python3", "scripts/n8n_import_diff.py"]),
]


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def sanitize(text: str) -> str:
    return text.replace(str(ROOT), "<repo>")


def compact_output(label: str, output: str) -> list[str]:
    lines = [sanitize(line.rstrip()) for line in output.splitlines() if line.strip()]
    if label == "Install-free public verification":
        passed = [line for line in lines if " passed" in line]
        return passed[-1:] or lines[-3:]
    if label == "Dry-run command waves":
        head = lines[:8]
        if len(lines) > 8:
            head.append("... workflow waves continue through archive/finalize/status")
        return head
    return lines[-4:]


def record_transcript() -> str:
    blocks: list[str] = []
    generated = datetime.now().astimezone().isoformat(timespec="seconds")
    blocks.append(f"# Daily Newsletter demo transcript")
    blocks.append(f"# generated_at={generated}")
    blocks.append("# source=real public verification commands; local paths sanitized")
    blocks.append("")
    for label, cmd in VERIFY_COMMANDS:
        display = " ".join(cmd)
        started = time.monotonic()
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=120)
        elapsed = time.monotonic() - started
        combined = "\n".join(part for part in (result.stdout, result.stderr) if part)
        blocks.append(f"## {label}")
        blocks.append(f"$ {display}")
        blocks.extend(compact_output(label, combined))
        blocks.append(f"exit={result.returncode} elapsed={elapsed:.1f}s")
        blocks.append("")
        if result.returncode != 0:
            raise RuntimeError(f"{display} failed with exit={result.returncode}")
    return "\n".join(blocks).strip() + "\n"


def visible_lines(transcript: str) -> list[str]:
    lines: list[str] = [
        "Use daily-newsletter to verify the public package",
        "",
    ]
    for raw in transcript.splitlines():
        if raw.startswith("# generated_at="):
            lines.append(raw.replace("# ", ""))
        elif raw.startswith("## "):
            lines.append("")
            lines.append(raw.removeprefix("## "))
        elif raw.startswith("$ ") or raw.startswith("PASS ") or raw.startswith("exit="):
            lines.append(raw)
        elif " passed" in raw or "workflow waves" in raw:
            lines.append(raw)
    lines.append("")
    lines.append("No production run. No Feishu or Telegram send.")
    return lines


def wrap_line(text: str, width: int = 82) -> list[str]:
    if not text:
        return [""]
    return textwrap.wrap(text, width=width, replace_whitespace=False) or [text]


def render_frame(lines: list[str], cursor: int, width: int, height: int) -> Image.Image:
    image = Image.new("RGB", (width, height), "#0f172a")
    draw = ImageDraw.Draw(image)
    mono = font(23)
    small = font(17)
    title = font(28)

    draw.rounded_rectangle((28, 24, width - 28, height - 24), radius=18, fill="#111827", outline="#334155", width=2)
    draw.text((52, 46), "Daily Newsletter", fill="#e2e8f0", font=title)
    draw.text((52, 82), "Agent skill public verification demo", fill="#94a3b8", font=small)
    draw.rectangle((52, 118, width - 52, 121), fill="#1f2937")

    wrapped: list[str] = []
    for line in lines[:cursor]:
        wrapped.extend(wrap_line(line))

    max_rows = 21
    viewport = wrapped[-max_rows:]
    y = 142
    for line in viewport:
        color = "#cbd5e1"
        if line.startswith("$ "):
            color = "#7dd3fc"
        elif line.startswith("PASS ") or " passed" in line or line.startswith("exit=0"):
            color = "#86efac"
        elif line.startswith("No production"):
            color = "#fbbf24"
        elif line and not line.startswith("#") and not line.startswith("...") and not line.startswith("generated_at"):
            color = "#e5e7eb"
        draw.text((56, y), line, fill=color, font=mono)
        y += 27

    draw.text((52, height - 54), "Generated from real verification commands; paths sanitized.", fill="#64748b", font=small)
    return image


def render_gif(transcript: str, output: Path) -> None:
    lines = visible_lines(transcript)
    frames: list[Image.Image] = []
    for cursor in range(4, len(lines) + 1):
        frames.append(render_frame(lines, cursor, width=1200, height=760))
    frames.extend([frames[-1]] * 4)
    output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=420,
        loop=0,
        optimize=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gif", type=Path, default=DEFAULT_GIF)
    parser.add_argument("--transcript", type=Path, default=DEFAULT_TRANSCRIPT)
    parser.add_argument("--from-transcript", action="store_true", help="Render from an existing transcript without rerunning commands.")
    args = parser.parse_args()

    if args.from_transcript:
        transcript = args.transcript.read_text(encoding="utf-8")
    else:
        transcript = record_transcript()
        args.transcript.parent.mkdir(parents=True, exist_ok=True)
        args.transcript.write_text(transcript, encoding="utf-8")

    render_gif(transcript, args.gif)
    print(args.gif)
    print(args.transcript)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
