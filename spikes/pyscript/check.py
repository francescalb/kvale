"""Headless smoke test and measurements for the PyScript spike.

Usage (from the repo root, with playwright installed and a server running):
    python -m http.server 8765 &
    python spikes/pyscript/check.py http://localhost:8765/spikes/pyscript/
"""

from __future__ import annotations

import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright

HERE = Path(__file__).parent
RESOURCES: list[tuple[int, str]] = []
URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8765/spikes/pyscript/"


async def load(page, cdp) -> tuple[float, int, int]:
    """Navigate and wait for the app; return (seconds, bytes, requests)."""
    total = {"bytes": 0, "n": 0}
    urls: dict[str, str] = {}

    def response(params):
        urls[params["requestId"]] = params["response"]["url"]

    def finished(params):
        size = params.get("encodedDataLength", 0)
        total["bytes"] += size
        total["n"] += 1
        RESOURCES.append((size, urls.get(params["requestId"], "?")))

    cdp.on("Network.responseReceived", response)
    cdp.on("Network.loadingFinished", finished)
    start = time.perf_counter()
    await page.goto(URL)
    await page.wait_for_function("window.kvaleReady === true", timeout=120_000)
    elapsed = time.perf_counter() - start
    await asyncio.sleep(0.5)
    cdp.remove_listener("Network.loadingFinished", finished)
    cdp.remove_listener("Network.responseReceived", response)
    return elapsed, total["bytes"], total["n"]


async def cell_center(page, x: int, y: int) -> tuple[float, float]:
    box = await page.locator("#grid").bounding_box()
    width = await page.evaluate("document.getElementById('grid').clientWidth")
    # Mirror the geometry in main.py: 12 columns, max 44px, centred, origin_y = 1.
    cell = max(4, min(44, (width - 2) // 12))
    origin_x = (width - 12 * cell) // 2
    return box["x"] + origin_x + (x + 0.5) * cell, box["y"] + 1 + (y + 0.5) * cell


async def main() -> None:
    results: dict[str, object] = {}
    errors: list[str] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(
            viewport={"width": 1200, "height": 820}, accept_downloads=True, locale="nb-NO"
        )
        page = await context.new_page()
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        page.on("pageerror", lambda e: errors.append(str(e)))
        cdp = await context.new_cdp_session(page)
        await cdp.send("Network.enable")

        t1, b1, n1 = await load(page, cdp)
        results["first_load_s"] = round(t1, 2)
        results["first_load_MB"] = round(b1 / 1e6, 2)
        results["first_load_requests"] = n1
        results["largest_resources_kB"] = [
            (round(size / 1e3), url.split("/")[-1]) for size, url in sorted(RESOURCES)[::-1][:8]
        ]

        t2, b2, n2 = await load(page, cdp)
        results["repeat_load_s"] = round(t2, 2)
        results["repeat_load_MB_transferred"] = round(b2 / 1e6, 2)

        # Paint a small motif with symmetry on.
        await page.check("input.sym[value=mirror_x]")
        await page.check("input.sym[value=mirror_y]")
        click_ms = []
        redraw_ms = []
        for i, (x, y) in enumerate([(1, 1), (2, 1), (1, 2), (3, 3), (4, 2), (2, 4), (5, 5)]):
            await page.click(f".swatch:nth-child({i % 3 + 1})")
            cx, cy = await cell_center(page, x, y)
            start = time.perf_counter()
            await page.mouse.click(cx, cy)
            click_ms.append((time.perf_counter() - start) * 1000)
            redraw_ms.append(float(await page.get_attribute("#grid", "data-redraw-ms")))
        # Recolour via a generated copy (mirror of (1,1) is (10,1)).
        await page.click(".swatch:nth-child(4)")
        cx, cy = await cell_center(page, 10, 1)
        await page.mouse.click(cx, cy)
        # Right-click erase on a generated copy of (5,5).
        cx, cy = await cell_center(page, 6, 6)
        await page.mouse.click(cx, cy, button="right")
        # Drag paint a diagonal.
        await page.click(".swatch:nth-child(2)")
        sx, sy = await cell_center(page, 0, 5)
        ex, ey = await cell_center(page, 0, 0)
        await page.mouse.move(sx, sy)
        await page.mouse.down()
        await page.mouse.move(ex, ey, steps=12)
        await page.mouse.up()
        motif = await page.evaluate("document.getElementById('status').textContent")
        results["edit_click_roundtrip_ms_median"] = round(statistics.median(click_ms), 1)
        results["edit_redraw_ms_median"] = round(statistics.median(redraw_ms), 2)
        results["status_after_edits"] = motif
        await page.screenshot(path=str(HERE / "screenshot-edit.png"))

        await page.click("#mode-preview")
        preview_ms = []
        for _ in range(5):
            await page.click("#mode-edit")
            await page.click("#mode-preview")
            preview_ms.append(float(await page.get_attribute("#grid", "data-redraw-ms")))
        results["preview_redraw_ms_median"] = round(statistics.median(preview_ms), 2)
        await page.screenshot(path=str(HERE / "screenshot-preview.png"))

        await page.select_option("#lang", "it")
        await page.wait_for_function("document.documentElement.lang === 'it'")
        results["label_it"] = await page.text_content("#mode-edit")
        await page.select_option("#lang", "en")
        await page.wait_for_function("document.documentElement.lang === 'en'")
        results["label_en"] = await page.text_content("#mode-edit")

        async with page.expect_download() as info:
            await page.click("#export-png")
        png = await (await info.value).path()
        results["png_bytes"] = Path(png).stat().st_size
        results["png_magic_ok"] = Path(png).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"

        async with page.expect_download() as info:
            await page.keyboard.press("Control+s")
        saved = json.loads(Path(await (await info.value).path()).read_text())
        results["json_marks"] = len(saved["motif"])
        results["json_symmetry"] = saved["symmetry"]

        await page.click("#clear")
        await page.set_input_files("#file-input", files=[{
            "name": "kvale.json", "mimeType": "application/json",
            "buffer": json.dumps(saved).encode(),
        }])
        await page.wait_for_function("document.getElementById('status').textContent.includes('kvale.json')")
        results["status_after_load"] = await page.text_content("#status")
        results["mirror_x_checked_after_load"] = await page.is_checked("input.sym[value=mirror_x]")

        await page.click("#mode-edit")
        await page.screenshot(path=str(HERE / "screenshot.png"))

        # Stress: bigger units and more repeats, random marks (see kvale_bench in main.py).
        bench = {}
        for w, rx, ry in [(24, 6, 2), (48, 8, 4), (100, 10, 4)]:
            bench[f"{w}x{w} unit, {rx}x{ry} repeats"] = await page.evaluate(
                f"window.kvaleBench({w}, {rx}, {ry})"
            )
        results["bench_ms"] = bench
        results["console_errors"] = errors
        await browser.close()
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
