#!/usr/bin/env python3
"""Render a local HTML file into one full-page PNG using Chrome DevTools."""
import argparse
import asyncio
import base64
import json
import socket
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

try:
    import websockets
except ModuleNotFoundError:
    websockets = None

try:
    from PIL import Image
except ModuleNotFoundError:
    Image = None

CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def trim_bottom_whitespace(path: Path, margin: int = 48, tolerance: int = 18) -> None:
    """Crop the fixed-height Chrome CLI tail when the page ends early."""
    if Image is None or not path.exists():
        return
    with Image.open(path) as img:
        rgb = img.convert("RGB")
        width, height = rgb.size
        if height <= 1200:
            return
        bg = rgb.getpixel((max(width - 2, 0), height - 2))
        step = max(width // 160, 1)

        def row_is_background(y: int) -> bool:
            for x in range(0, width, step):
                pixel = rgb.getpixel((x, y))
                if any(abs(pixel[i] - bg[i]) > tolerance for i in range(3)):
                    return False
            return True

        last_content_y = height - 1
        while last_content_y > 0 and row_is_background(last_content_y):
            last_content_y -= 1
        crop_bottom = min(height, last_content_y + margin)
        if crop_bottom < height - 100:
            img.crop((0, 0, width, crop_bottom)).save(path)


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_json(url: str, timeout: float = 8.0) -> dict:
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                return json.loads(resp.read())
        except Exception as exc:
            last_error = exc
            time.sleep(0.1)
    raise RuntimeError(f"Chrome DevTools did not start: {last_error}")


async def render(html: Path, output: Path, width: int) -> None:
    if not CHROME.exists():
        raise RuntimeError(f"Chrome not found: {CHROME}")
    port = free_port()
    with tempfile.TemporaryDirectory(prefix="parkio-chrome-") as user_data:
        proc = subprocess.Popen(
            [
                str(CHROME),
                "--headless=new",
                "--hide-scrollbars",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--no-first-run",
                "--no-default-browser-check",
                f"--user-data-dir={user_data}",
                f"--remote-debugging-port={port}",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            targets = wait_json(f"http://127.0.0.1:{port}/json")
            page = next((t for t in targets if t.get("type") == "page" and t.get("webSocketDebuggerUrl")), None)
            if not page:
                raise RuntimeError("Chrome page target not found")
            ws_url = page["webSocketDebuggerUrl"]
            async with websockets.connect(ws_url, max_size=80_000_000) as ws:
                seq = 0
                pending: dict[int, asyncio.Future] = {}
                events: asyncio.Queue = asyncio.Queue()

                async def reader() -> None:
                    async for raw in ws:
                        msg = json.loads(raw)
                        if "id" in msg and msg["id"] in pending:
                            pending.pop(msg["id"]).set_result(msg)
                        else:
                            await events.put(msg)

                reader_task = asyncio.create_task(reader())

                async def send(method: str, params: dict | None = None) -> dict:
                    nonlocal seq
                    seq += 1
                    fut = asyncio.get_running_loop().create_future()
                    pending[seq] = fut
                    await ws.send(json.dumps({"id": seq, "method": method, "params": params or {}}))
                    msg = await asyncio.wait_for(fut, timeout=20)
                    if "error" in msg:
                        raise RuntimeError(f"{method} failed: {msg['error']}")
                    return msg.get("result", {})

                await send("Page.enable")
                await send("Runtime.enable")
                await send(
                    "Emulation.setDeviceMetricsOverride",
                    {
                        "width": width,
                        "height": 900,
                        "deviceScaleFactor": 1,
                        "mobile": False,
                    },
                )
                file_url = "file://" + urllib.parse.quote(str(html.resolve()))
                await send("Page.navigate", {"url": file_url})

                deadline = time.time() + 20
                while time.time() < deadline:
                    try:
                        event = await asyncio.wait_for(events.get(), timeout=1)
                    except asyncio.TimeoutError:
                        continue
                    if event.get("method") == "Page.loadEventFired":
                        break
                await asyncio.sleep(0.5)

                metrics = await send(
                    "Runtime.evaluate",
                    {
                        "expression": """
(() => {
  const body = document.body;
  const html = document.documentElement;
  return {
    width: Math.ceil(Math.max(body.scrollWidth, html.scrollWidth, body.offsetWidth, html.offsetWidth, body.clientWidth, html.clientWidth)),
    height: Math.ceil(Math.max(body.scrollHeight, html.scrollHeight, body.offsetHeight, html.offsetHeight, body.clientHeight, html.clientHeight))
  };
})()
""",
                        "returnByValue": True,
                    },
                )
                value = metrics["result"]["value"]
                page_width = min(max(int(value.get("width") or width), width), 1600)
                page_height = max(int(value.get("height") or 900), 900)
                await send(
                    "Emulation.setDeviceMetricsOverride",
                    {
                        "width": page_width,
                        "height": min(page_height, 900),
                        "deviceScaleFactor": 1,
                        "mobile": False,
                    },
                )
                screenshot = await send(
                    "Page.captureScreenshot",
                    {
                        "format": "png",
                        "fromSurface": True,
                        "captureBeyondViewport": True,
                        "clip": {
                            "x": 0,
                            "y": 0,
                            "width": page_width,
                            "height": page_height,
                            "scale": 1,
                        },
                    },
                )
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(base64.b64decode(screenshot["data"]))
                trim_bottom_whitespace(output)
                reader_task.cancel()
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


def render_with_chrome_cli(html: Path, output: Path, width: int) -> None:
    """Fallback renderer for launchd Python environments without websockets."""
    if not CHROME.exists():
        raise RuntimeError(f"Chrome not found: {CHROME}")
    output.parent.mkdir(parents=True, exist_ok=True)
    height = 16000
    file_url = "file://" + urllib.parse.quote(str(html.resolve()))
    with tempfile.TemporaryDirectory(prefix="parkio-chrome-cli-") as user_data:
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
                    f"--screenshot={output}",
                    file_url,
                ],
                capture_output=True,
                text=True,
                timeout=90,
            )
        except subprocess.TimeoutExpired as exc:
            if output.exists() and output.stat().st_size > 0:
                return
            raise RuntimeError(f"Chrome CLI screenshot timed out: {exc}") from exc
    if result.returncode != 0 or not output.exists():
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"Chrome CLI screenshot failed: {detail}")
    trim_bottom_whitespace(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("html", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--width", type=int, default=1200)
    args = parser.parse_args()
    if websockets is None:
        render_with_chrome_cli(args.html, args.output, args.width)
    else:
        asyncio.run(render(args.html, args.output, args.width))
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
