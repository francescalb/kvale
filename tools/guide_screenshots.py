"""Take the screenshots for the user guide (``web/guide/img/``) from the real app.

    pip install -e '.[browser]' && playwright install chromium
    python tools/guide_screenshots.py

Builds the site, serves it, opens the example pattern in headless Chromium in
each language and saves small WebP images: the drawing view, an end piece, the
colour dialog and the whole band. Run it again when the look changes.
"""

from __future__ import annotations

import functools
import http.server
import importlib.util
import io
import tempfile
import threading
from pathlib import Path
from typing import Any

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "guide" / "img"
LANGUAGES = ("nb", "en", "it")
WIDTH = 880  # pixels; the guide shows them at most this wide
QUALITY = 72


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        pass


def _build(out: Path) -> None:
    spec = importlib.util.spec_from_file_location("build_site", ROOT / "tools" / "build_site.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.build(out)


def save(png: bytes, name: str, width: int = WIDTH) -> None:
    image = Image.open(io.BytesIO(png)).convert("RGB")
    if image.width > width:
        image = image.resize(
            (width, round(image.height * width / image.width)), Image.Resampling.LANCZOS
        )
    path = OUT / f"{name}.webp"
    image.save(path, "WEBP", quality=QUALITY, method=6)
    print(f"Wrote {path} ({path.stat().st_size // 1024} KB)")


def shoot(page: Any, url: str, lang: str) -> None:
    page.goto(url + "i18n/nb.json")
    page.evaluate(
        """(lang) => {
            localStorage.clear();
            localStorage.setItem('kvale-lang', lang);
            localStorage.setItem('kvale-theme', 'light');
        }""",
        lang,
    )
    page.goto(url + "?example=flower-band")
    page.wait_for_function("window.kvaleReady === true", timeout=120_000)
    page.wait_for_function("(document.getElementById('doc-name') || {}).textContent")
    page.mouse.move(0, 0)
    page.wait_for_timeout(300)
    save(page.screenshot(), f"{lang}-draw")

    page.click("#target-seg [data-target=right]")
    page.wait_for_timeout(300)
    save(page.locator("#stage").screenshot(), f"{lang}-end", width=700)
    page.click("#target-seg [data-target=unit]")

    page.click("#colour-slots .slot:nth-child(1) .slot-edit")
    page.wait_for_selector("#colour-dialog[open]")
    page.wait_for_timeout(300)
    save(page.locator("#colour-dialog").screenshot(), f"{lang}-colour", width=560)
    page.keyboard.press("Escape")

    page.click("#mode-preview")
    page.wait_for_timeout(300)
    save(page.locator("#stage").screenshot(), f"{lang}-band", width=700)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _build(root / "kvale")
        handler = functools.partial(_QuietHandler, directory=str(root))
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{server.server_address[1]}/kvale/"
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                context = browser.new_context(
                    viewport={"width": 1280, "height": 860}, service_workers="block"
                )
                for lang in LANGUAGES:
                    page = context.new_page()
                    page.on("dialog", lambda dialog: dialog.accept())
                    shoot(page, url, lang)
                    page.close()
                browser.close()
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
