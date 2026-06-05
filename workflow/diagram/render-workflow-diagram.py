#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import math
import subprocess
import sys
import textwrap
from pathlib import Path

import yaml


PALETTE = {
    "script":      ("#0f766e", "#e6fcf5", "脚本 / 确定性"),
    "ai":          ("#b45309", "#fff7ed", "AI + system prompt"),
    "local_model": ("#7c3aed", "#f5f3ff", "本地模型 / MLX Whisper"),
    "human":       ("#2563eb", "#eff6ff", "Human 输入"),
    "entry":       ("#475569", "#f1f5f9", "自动抓取入口"),
    "state":       ("#64748b", "#f8fafc", "状态与归档"),
    "output":      ("#0f3d38", "#ecfdf5", "最终输出"),
    "sink":        ("#166534", "#f0fdf4", "Section Sink"),
    # legacy aliases kept for edge colour lookup
    "media":       ("#7c3aed", "#f5f3ff", "本地模型 / MLX Whisper"),
    "manual":      ("#2563eb", "#eff6ff", "Human 输入"),
    "bypass":      ("#0f766e", "#e6fcf5", "脚本 / 确定性"),
}

DEFAULT_W = 1720
DEFAULT_H = 1940


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def wrap_line(text: str, max_chars: int) -> list[str]:
    wrapped: list[str] = []
    for para in str(text).splitlines():
        wrapped.extend(textwrap.wrap(para, width=max_chars, break_long_words=False) or [""])
    return wrapped


def node_svg(node: dict) -> str:
    color, fill, type_label = PALETTE[node["type"]]
    x, y, w, h = node["x"], node["y"], node["w"], node["h"]
    max_chars = max(14, math.floor((w - 38) / 12))
    out = [
        f'<g id="node-{esc(node["id"])}">',
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="{fill}" stroke="{color}" stroke-width="3" filter="url(#shadow)"/>',
        f'<text x="{x + 20}" y="{y + 28}" fill="{color}" font-size="13" font-weight="850" letter-spacing="1">{esc(type_label)}</text>',
    ]
    yy = y + 62
    for line in wrap_line(node["title"], max_chars):
        out.append(f'<text x="{x + 20}" y="{yy}" fill="#111827" font-size="24" font-weight="850">{esc(line)}</text>')
        yy += 30
    yy += 2
    for body in node.get("body", []):
        for line in wrap_line(body, max_chars):
            if yy > y + h - 16:
                break
            out.append(f'<text x="{x + 20}" y="{yy}" fill="#64748b" font-size="16" font-weight="520">{esc(line)}</text>')
            yy += 22
        if yy > y + h - 16:
            break
    components = node.get("components") or []
    if components and yy < y + h - 70:
        yy += 10
        out.append(f'<line x1="{x + 20}" y1="{yy}" x2="{x + w - 20}" y2="{yy}" stroke="{color}" stroke-width="2" opacity=".18"/>')
        yy += 30
        for component in components:
            if yy > y + h - 38:
                break
            out.append(f'<text x="{x + 20}" y="{yy}" fill="{color}" font-size="14" font-weight="850">{esc(component.get("title", component.get("id", "")))}</text>')
            yy += 22
            for body in component.get("body", [])[:2]:
                for line in wrap_line(body, max_chars - 2):
                    if yy > y + h - 22:
                        break
                    out.append(f'<text x="{x + 34}" y="{yy}" fill="#64748b" font-size="13" font-weight="520">{esc(line)}</text>')
                    yy += 18
                if yy > y + h - 22:
                    break
            yy += 10
    out.append("</g>")
    return "\n".join(out)


def edge_anchor(node: dict, side: str) -> tuple[float, float]:
    x, y, w, h = node["x"], node["y"], node["w"], node["h"]
    if side == "right":
        return x + w, y + h / 2
    if side == "left":
        return x, y + h / 2
    if side == "top":
        return x + w / 2, y
    if side == "bottom":
        return x + w / 2, y + h
    raise ValueError(side)


def side_pair(a: dict, b: dict) -> tuple[str, str]:
    ac = (a["x"] + a["w"] / 2, a["y"] + a["h"] / 2)
    bc = (b["x"] + b["w"] / 2, b["y"] + b["h"] / 2)
    dx, dy = bc[0] - ac[0], bc[1] - ac[1]
    if abs(dx) >= abs(dy):
        return ("right", "left") if dx >= 0 else ("left", "right")
    return ("bottom", "top") if dy >= 0 else ("top", "bottom")


def path_between(a: dict, b: dict) -> tuple[str, str, str]:
    a_side, b_side = side_pair(a, b)
    x1, y1 = edge_anchor(a, a_side)
    x2, y2 = edge_anchor(b, b_side)
    if a_side in {"right", "left"}:
        mid = (x1 + x2) / 2
        d = f"M {x1:.1f} {y1:.1f} C {mid:.1f} {y1:.1f}, {mid:.1f} {y2:.1f}, {x2:.1f} {y2:.1f}"
    else:
        mid = (y1 + y2) / 2
        d = f"M {x1:.1f} {y1:.1f} C {x1:.1f} {mid:.1f}, {x2:.1f} {mid:.1f}, {x2:.1f} {y2:.1f}"
    return d, a_side, b_side


def edge_svg(edge: dict, nodes: dict[str, dict]) -> str:
    color = PALETTE[edge.get("type", "state")][0]
    if edge.get("points"):
        points = edge["points"]
        start_side = edge.get("start", "right")
        end_side = edge.get("end", "left")
        start = edge_anchor(nodes[edge["from"]], start_side)
        end = edge_anchor(nodes[edge["to"]], end_side)
        all_points = [start, *[(p["x"], p["y"]) for p in points], end]
        d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in all_points)
    else:
        d, _, _ = path_between(nodes[edge["from"]], nodes[edge["to"]])
    marker = f"arrow-{edge.get('type', 'state')}"
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" marker-end="url(#{marker})" opacity="0.92"/>'


def layout(data: dict) -> dict:
    nodes = [dict(n) for n in data["nodes"]]
    lane_by_id = {lane["id"]: lane for lane in data["lanes"]}
    by_lane: dict[str, list[dict]] = {}
    for node in nodes:
        by_lane.setdefault(node["lane"], []).append(node)

    for lane_id, lane_nodes in by_lane.items():
        lane = lane_by_id[lane_id]
        top = lane["y"] + 42
        gap = 34 if lane_id != "deliver" else 40
        if lane_id == "deliver":
            auto_nodes = [node for node in lane_nodes if not {"x", "y", "w", "h"} <= set(node)]
            explicit_nodes = [node for node in lane_nodes if {"x", "y", "w", "h"} <= set(node)]
            if explicit_nodes:
                continue
            columns = min(5, max(1, len(auto_nodes)))
            gap_x = 70
            node_w = int((lane["w"] - 140 - gap_x * (columns - 1)) / columns)
            for i, node in enumerate(auto_nodes):
                row = i // columns
                col = i % columns
                node["x"] = lane["x"] + 70 + col * (node_w + gap_x)
                node["y"] = top + row * 166
                node["w"] = node_w
                node["h"] = 126
            continue
        auto_nodes = [node for node in lane_nodes if not {"x", "y", "w", "h"} <= set(node)]
        if len(auto_nodes) != len(lane_nodes):
            continue
        available = lane["h"] - 92
        base_h = min(148, max(112, (available - gap * (len(auto_nodes) - 1)) // len(auto_nodes)))
        for idx, node in enumerate(auto_nodes):
            node["x"] = lane["x"] + 34
            node["y"] = top + idx * (base_h + gap)
            node["w"] = lane["w"] - 68
            node["h"] = base_h
            if node["id"] in {"transcribe_media", "score_ordinary", "quality_gate"}:
                node["h"] += 18

    data = dict(data)
    data["nodes"] = nodes
    return data


_LEGEND_TYPES = ["entry", "human", "script", "local_model", "ai", "sink", "state", "output"]


def render_html(data: dict) -> str:
    canvas = data.get("canvas") or {}
    W = int(canvas.get("w", DEFAULT_W))
    H = int(canvas.get("h", DEFAULT_H))
    data = layout(data)
    nodes = {node["id"]: node for node in data["nodes"]}
    legend = "\n".join(
        f'<span class="pill"><span style="background:{PALETTE[name][0]}"></span>{esc(PALETTE[name][2])}</span>'
        for name in _LEGEND_TYPES
    )
    markers = "\n".join(
        f'<marker id="arrow-{name}" markerWidth="14" markerHeight="14" refX="11" refY="7" orient="auto"><path d="M2,2 L12,7 L2,12" fill="none" stroke="{color}" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"/></marker>'
        for name, (color, _, _) in PALETTE.items()
    )
    lanes = "\n".join(
        f'<rect x="{lane["x"]}" y="{lane["y"]}" width="{lane["w"]}" height="{lane["h"]}" rx="24" fill="#ffffff" opacity=".5" stroke="#94a3b8" stroke-width="2" stroke-dasharray="10 9"/><rect x="{lane["x"] + 24}" y="{lane["y"] - 17}" width="{len(lane["title"]) * 17 + 26}" height="34" rx="10" fill="#fffdf8"/><text x="{lane["x"] + 38}" y="{lane["y"] + 7}" fill="#64748b" font-size="18" font-weight="850">{esc(lane["title"])}</text>'
        for lane in data["lanes"]
    )
    edges = "\n".join(edge_svg(edge, nodes) for edge in data["edges"])
    node_markup = "\n".join(node_svg(node) for node in data["nodes"])
    notes = "".join(f"<li>{esc(note)}</li>" for note in data.get("notes", []))
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(data["title"])} — {esc(data["version"])}</title>
  <style>
    body {{ margin: 0; background: #f7f3ea; color: #111827; font-family: Inter, "SF Pro Text", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    main {{ width: {W}px; margin: 0 auto; padding: 34px 40px 48px; }}
    .top {{ display: flex; justify-content: space-between; gap: 28px; align-items: flex-start; margin-bottom: 20px; }}
    h1 {{ margin: 0; font-size: 42px; letter-spacing: 0; }}
    .sub {{ margin: 10px 0 0; color: #64748b; font-size: 18px; }}
    .legend {{ display: flex; flex-wrap: wrap; gap: 10px; justify-content: flex-end; max-width: 1050px; }}
    .pill {{ display: inline-flex; align-items: center; gap: 8px; border: 2px solid #d8d0c3; background: #fffdf8; border-radius: 999px; padding: 8px 12px; font-size: 15px; font-weight: 760; }}
    .pill span {{ display: inline-block; width: 12px; height: 12px; border-radius: 999px; }}
    .canvas {{ border: 2px solid #d8d0c3; border-radius: 24px; overflow: hidden; background: #fffdf8; box-shadow: 0 18px 50px rgba(31,41,51,.09); }}
    svg {{ display: block; width: 100%; height: auto; }}
    .notes {{ margin: 18px 0 0; color: #64748b; font-size: 16px; line-height: 1.7; }}
  </style>
</head>
<body>
<main>
  <div class="top">
    <div>
      <h1>{esc(data["title"])} {esc(data["version"].upper())}</h1>
      <p class="sub">{esc(data["subtitle"])}</p>
    </div>
    <div class="legend">{legend}</div>
  </div>
  <div class="canvas">
  <svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{esc(data["title"])}">
    <defs>
      <filter id="shadow" x="-8%" y="-8%" width="125%" height="125%"><feDropShadow dx="4" dy="6" stdDeviation="0" flood-color="#1f2933" flood-opacity=".10"/></filter>
      <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.1" fill="#1f2933" opacity=".10"/></pattern>
      {markers}
    </defs>
    <rect x="0" y="0" width="{W}" height="{H}" fill="#fffdf8"/>
    <rect x="0" y="0" width="{W}" height="{H}" fill="url(#grid)"/>
    {lanes}
    {edges}
    {node_markup}
  </svg>
  </div>
  <ul class="notes">{notes}</ul>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="/Users/wendy/park-io/inbox/inbox-workflow.yaml")
    parser.add_argument("--html", default="/Users/wendy/park-io/inbox/inbox-workflow.html")
    parser.add_argument("--png", default="/Users/wendy/park-io/inbox/inbox-workflow.png")
    parser.add_argument("--json", default="/Users/wendy/park-io/inbox/inbox-workflow.json")
    args = parser.parse_args()

    validator = Path(__file__).with_name("validate-workflow.py")
    if validator.exists():
        subprocess.run([sys.executable, str(validator), args.input], check=True)

    data = yaml.safe_load(Path(args.input).read_text(encoding="utf-8"))
    html_text = render_html(data)
    Path(args.html).write_text(html_text, encoding="utf-8")
    Path(args.json).write_text(json.dumps(layout(data), ensure_ascii=False, indent=2), encoding="utf-8")
    canvas = data.get("canvas") or {}
    canvas_w = int(canvas.get("w", DEFAULT_W))
    canvas_h = int(canvas.get("h", DEFAULT_H))
    # Page includes header (~180px) + canvas + notes (~80px). Scale Chrome window
    # so the screenshot includes the full page without scrollbars.
    window_w = canvas_w + 80
    window_h = canvas_h + 260
    subprocess.run(
        [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "--headless",
            "--disable-gpu",
            "--hide-scrollbars",
            f"--window-size={window_w},{window_h}",
            f"--screenshot={args.png}",
            Path(args.html).as_uri(),
        ],
        check=True,
    )
    print(args.html)
    print(args.png)
    print(args.json)


if __name__ == "__main__":
    main()
