"""Browser smoke tests for the web app (headless Chromium through Playwright).

These build ``_site`` into a temporary folder, serve it, and drive the real app.
They need network access (PyScript and Pyodide come from their CDNs), so they
are marked ``browser`` and left out of the default run. Run them with::

    pip install playwright && playwright install chromium
    pytest -m browser

They are skipped when Playwright or Chromium is not installed.
"""

from __future__ import annotations

import functools
import http.server
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.browser

sync_api = pytest.importorskip("playwright.sync_api")

ROOT = Path(__file__).resolve().parent.parent
BOOT_TIMEOUT_MS = 120_000
RED = (0xB1, 0x17, 0x2B)  # colour slot 1 in the default palette
GREEN = (0x2D, 0x7D, 0x32)  # colour slot 2
WHITE = (0xFF, 0xFF, 0xFF)  # default background
GREY = (0x63, 0x5A, 0x50)  # --text-muted (light), laid over cells outside the minimal cell
DIM_ALPHA = 0.2  # kvale_web.grid.canvas.DIM_ALPHA


def dimmed(colour: tuple[int, int, int]) -> tuple[int, int, int]:
    """How a cell colour looks outside the minimal cell."""
    r, g, b = (round(c * (1 - DIM_ALPHA) + bg * DIM_ALPHA) for c, bg in zip(colour, GREY, strict=True))
    return r, g, b


def close(actual: tuple[int, int, int], expected: tuple[int, int, int]) -> bool:
    return all(abs(a - e) <= 2 for a, e in zip(actual, expected, strict=True))


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        pass


@pytest.fixture(scope="session")
def site_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    import importlib.util

    spec = importlib.util.spec_from_file_location("build_site", ROOT / "tools" / "build_site.py")
    assert spec and spec.loader
    build_site = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build_site)
    # Serve under a sub-path, like GitHub Pages does (/kvale/).
    root = tmp_path_factory.mktemp("pages")
    build_site.build(root / "kvale")

    handler = functools.partial(_QuietHandler, directory=str(root))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/kvale/"
    server.shutdown()
    server.server_close()


@pytest.fixture(scope="session")
def browser() -> Iterator[Any]:
    with sync_api.sync_playwright() as playwright:
        try:
            launched = playwright.chromium.launch()
        except sync_api.Error as error:
            pytest.skip(f"Chromium is not available: {error}")
        yield launched
        launched.close()


@pytest.fixture(scope="session")
def context(browser: Any) -> Iterator[Any]:
    # One context for the session so the CDN files come from the HTTP cache.
    ctx = browser.new_context(viewport={"width": 1200, "height": 820}, locale="nb-NO")
    yield ctx
    ctx.close()


class App:
    """A loaded page plus the console errors and requests it produced."""

    def __init__(self, page: Any, url: str) -> None:
        self.page = page
        self.url = url
        self.errors: list[str] = []
        self.requests: list[str] = []
        page.on("console", self._on_console)
        page.on("pageerror", lambda error: self.errors.append(str(error)))
        page.on("request", lambda request: self.requests.append(request.url))

    def _on_console(self, message: Any) -> None:
        if message.type == "error":
            self.errors.append(message.text)

    def load(self) -> App:
        self.page.goto(self.url)
        self.page.wait_for_function("window.kvaleReady === true", timeout=BOOT_TIMEOUT_MS)
        return self

    def cell_centre(self, x: int, y: int) -> tuple[float, float]:
        canvas = self.page.locator("#grid")
        box = canvas.bounding_box()
        size = float(canvas.get_attribute("data-cell-size"))
        origin_x = float(canvas.get_attribute("data-origin-x"))
        origin_y = float(canvas.get_attribute("data-origin-y"))
        return box["x"] + origin_x + (x + 0.5) * size, box["y"] + origin_y + (y + 0.5) * size

    def click_cell(self, x: int, y: int, button: str = "left") -> None:
        self.page.mouse.click(*self.cell_centre(x, y), button=button)

    def colour(self, x: int, y: int) -> tuple[int, int, int]:
        """Colour drawn at the centre of a unit cell (with the pointer off the canvas)."""
        self.page.mouse.move(0, 0)  # remove the hover tint
        rgba = self.page.evaluate(
            """([x, y]) => {
                const canvas = document.getElementById('grid');
                const d = canvas.dataset, r = window.devicePixelRatio || 1;
                const px = (+d.originX + (x + 0.5) * +d.cellSize) * r;
                const py = (+d.originY + (y + 0.5) * +d.cellSize) * r;
                return Array.from(canvas.getContext('2d').getImageData(px, py, 1, 1).data);
            }""",
            [x, y],
        )
        return rgba[0], rgba[1], rgba[2]


@pytest.fixture
def app(context: Any, site_url: str) -> Iterator[App]:
    page = context.new_page()
    # Start from a clean localStorage (it is shared by the whole context).
    page.goto(site_url + "i18n/nb.json")
    page.evaluate("localStorage.clear()")
    loaded = App(page, site_url).load()
    yield loaded
    page.close()
    assert loaded.errors == [], f"Console errors: {loaded.errors}"


def test_boots_without_errors_or_pillow(app: App) -> None:
    assert app.page.is_hidden("#boot")
    assert app.page.text_content("#mode-edit") == "Tegn"
    assert app.page.is_disabled("#undo")
    assert not [url for url in app.requests if "pillow" in url.lower()]


def test_paint_mirror_erase_and_undo(app: App) -> None:
    page = app.page
    assert page.is_hidden("#minimal-cell-hint")
    page.check("input.sym[value=mirror_x]")
    assert page.is_visible("#minimal-cell-hint")
    app.click_cell(1, 1)
    assert app.colour(1, 1) == RED
    assert close(app.colour(10, 1), dimmed(RED))  # generated by mirror_x, drawn dimmed

    page.click(".swatch:nth-child(2)")
    app.click_cell(1, 1)
    assert app.colour(1, 1) == GREEN
    assert close(app.colour(10, 1), dimmed(GREEN))

    app.click_cell(1, 1, button="right")
    assert app.colour(1, 1) == WHITE
    assert close(app.colour(10, 1), dimmed(WHITE))

    page.click("#undo")
    assert app.colour(1, 1) == GREEN
    page.keyboard.press("Control+z")
    assert app.colour(1, 1) == RED
    page.keyboard.press("Control+y")
    assert app.colour(1, 1) == GREEN
    page.click("#redo")
    assert app.colour(1, 1) == WHITE
    assert page.is_disabled("#redo")

    # Undoing the symmetry change unticks the checkbox again.
    for _ in range(4):
        page.click("#undo")
    assert not page.is_checked("input.sym[value=mirror_x]")
    assert page.is_disabled("#undo")
    assert page.is_hidden("#minimal-cell-hint")
    assert app.colour(10, 1) == WHITE  # the whole unit is editable again


def test_click_outside_minimal_cell_does_nothing(app: App) -> None:
    page = app.page
    page.check("input.sym[value=mirror_x]")
    page.check("input.sym[value=mirror_y]")  # minimal cell: the top-left 6x6 quarter
    app.click_cell(8, 2)
    app.click_cell(2, 8)
    app.click_cell(8, 8)
    assert close(app.colour(8, 2), dimmed(WHITE))
    assert close(app.colour(2, 8), dimmed(WHITE))
    assert close(app.colour(8, 8), dimmed(WHITE))
    assert app.colour(3, 3) == WHITE

    app.click_cell(2, 2)  # inside: mirrored into the other three quarters
    assert app.colour(2, 2) == RED
    for x, y in [(9, 2), (2, 9), (9, 9)]:
        assert close(app.colour(x, y), dimmed(RED)), (x, y)
    app.click_cell(9, 9, button="right")  # erasing a copy does nothing either
    assert app.colour(2, 2) == RED

    page.keyboard.press("Control+z")
    assert app.colour(2, 2) == WHITE
    page.keyboard.press("Control+z")
    page.keyboard.press("Control+z")
    assert page.is_disabled("#undo")  # the outside clicks made no undo steps


def test_drag_stroke_is_one_undo_step(app: App) -> None:
    page = app.page
    page.mouse.move(*app.cell_centre(0, 5))
    page.mouse.down()
    page.mouse.move(*app.cell_centre(0, 0), steps=12)
    page.mouse.up()
    assert all(app.colour(0, y) == RED for y in range(6))
    page.keyboard.press("Control+z")
    assert all(app.colour(0, y) == WHITE for y in range(6))
    assert page.is_disabled("#undo")


def test_eraser_toggle(app: App) -> None:
    app.click_cell(3, 3)
    app.page.click("#tool-unpick")
    assert app.page.get_attribute("#tool-unpick", "aria-pressed") == "true"
    app.click_cell(3, 3)
    assert app.colour(3, 3) == WHITE
    app.page.click(".swatch:nth-child(1)")  # choosing a colour leaves the eraser
    assert app.page.get_attribute("#tool-cross", "aria-pressed") == "true"
    assert app.page.get_attribute("#tool-unpick", "aria-pressed") == "false"
    app.page.keyboard.press("e")  # shortcut for unpick
    assert app.page.get_attribute("#tool-unpick", "aria-pressed") == "true"


def test_preview_mode(app: App) -> None:
    page = app.page
    app.click_cell(0, 0)
    edit_size = float(page.get_attribute("#grid", "data-cell-size"))
    page.click("#mode-preview")
    assert page.get_attribute("#mode-preview", "aria-pressed") == "true"
    assert float(page.get_attribute("#grid", "data-cell-size")) < edit_size
    # Default 12x12 unit repeated 6x2; cell (12, 0) is the next repeat's (0, 0).
    assert app.colour(12, 0) == RED
    page.keyboard.press("p")
    assert page.get_attribute("#mode-edit", "aria-pressed") == "true"


def test_language_switch_and_memory(app: App) -> None:
    page = app.page
    page.click("#lang-seg [data-lang=it]")
    page.wait_for_function("document.documentElement.lang === 'it'")
    assert page.text_content("#mode-edit") == "Disegna"
    assert page.text_content("#canvas-hint").startswith("Tocca o trascina")
    assert page.get_attribute(".swatch:nth-child(1)", "aria-label") == "Colore 1"
    page.click("#lang-seg [data-lang=en]")
    page.wait_for_function("document.documentElement.lang === 'en'")
    assert page.text_content("#mode-edit") == "Draw"
    app.load()  # reload: the choice is remembered
    assert page.text_content("#mode-edit") == "Draw"
    assert page.get_attribute("#lang-seg [data-lang=en]", "aria-pressed") == "true"
    assert page.get_attribute("#lang-seg [data-lang=nb]", "aria-pressed") == "false"


def test_language_from_browser(browser: Any, site_url: str) -> None:
    ctx = browser.new_context(locale="it-IT")
    try:
        app = App(ctx.new_page(), site_url).load()
        assert app.page.text_content("#mode-edit") == "Disegna"
        assert app.errors == []
    finally:
        ctx.close()


def run_python(app: App, code: str) -> None:
    """Run ``code`` in the page's interpreter; it must set ``window.kvaleDone``."""
    app.page.evaluate(
        """code => {
            window.kvaleDone = undefined;
            const script = document.createElement('script');
            script.type = 'py';
            script.textContent = code;
            document.body.append(script);
        }""",
        code,
    )
    app.page.wait_for_function("window.kvaleDone !== undefined", timeout=30_000)


def test_core_package_data_and_example_load(app: App) -> None:
    from kvale.core import build_colour_grid
    from kvale.core.serialization import load_document

    example = ROOT / "examples" / "flower-band.json"
    app.page.evaluate("text => { window.kvaleExample = text; }", example.read_text("utf-8"))
    run_python(
        app,
        """
import json
from pyscript import window
from kvale.core.dmc import load_dmc_colours
from kvale.core.model import PatternDocument
from kvale_web import app as kvale_app

document = PatternDocument.from_dict(json.loads(window.kvaleExample))
kvale_app.app.state.load(document)
window.kvaleDone = len(load_dmc_colours())
""",
    )
    assert app.page.evaluate("window.kvaleDone") > 400  # dmc_palette.json was fetched
    assert app.page.is_disabled("#undo")  # loading resets the history

    # The preview shows the example's repeats, cell for cell.
    grid = build_colour_grid(load_document(example))
    app.page.click("#mode-preview")
    for x, y in [(0, 0), (5, 3), (17, 9), (40, 20), (83, 23)]:
        expected = tuple(bytes.fromhex(grid[y][x].lstrip("#")))
        assert app.colour(x, y) == expected, (x, y)


def test_theme_switch_and_memory(app: App) -> None:
    page = app.page
    light_bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
    page.click("#theme-seg [data-theme-set=dark]")
    assert page.get_attribute("html", "data-theme") == "dark"
    assert page.get_attribute("#theme-seg [data-theme-set=dark]", "aria-pressed") == "true"
    assert page.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(27, 24, 21)"
    assert light_bg == "rgb(244, 239, 230)"
    app.load()  # reload: the choice is remembered (applied before Python starts)
    assert page.get_attribute("html", "data-theme") == "dark"
    page.click("#theme-seg [data-theme-set=light]")
    assert page.evaluate("getComputedStyle(document.body).backgroundColor") == light_bg


def test_tool_hint_and_backstitch_placeholder(app: App) -> None:
    page = app.page
    assert page.text_content("#canvas-hint").startswith("Trykk eller dra")
    assert page.is_disabled("#tool-back")  # switched on by chunk 4
    page.click("#tool-unpick")
    assert page.text_content("#canvas-hint").startswith("Trykk på et sting")


def test_mode_hides_edit_only_parts(app: App) -> None:
    page = app.page
    assert page.is_visible("#edit-side")
    assert page.is_hidden("#preview-side")
    page.click("#mode-preview")
    assert page.get_attribute("#stage", "data-mode") == "preview"
    assert page.is_hidden("#edit-side")
    assert page.is_visible("#preview-side")


def test_toast_shows_status_with_undo(app: App) -> None:
    page = app.page
    assert page.is_hidden("#toast")
    app.click_cell(0, 0)
    run_python(
        app,
        """
from pyscript import window
from kvale_web import app as kvale_app

kvale_app.app.state.set_status("symmetry.switchedOff")
window.kvaleDone = True
""",
    )
    assert page.is_visible("#toast")
    assert page.text_content("#toast-message").startswith("Rapporten er ikke kvadratisk")
    page.click("#toast-undo")
    assert app.colour(0, 0) == WHITE
    assert page.text_content("#toast-message") == "Angret."
    assert page.is_hidden("#toast-undo")


# Every region a later chunk fills in (see web/README.md).
OWNED_CONTAINERS = [
    "doc-info", "file-actions",  # chunk 6
    "tool-seg", "zoom-controls", "target-bar", "target-seg", "corner-seg", "end-panel",
    "ruler-top", "ruler-left", "grid", "edge-popover", "legend", "canvas-hint",
    "mini-band", "preview-caption", "reset-dialog",  # chunk 4
    "colours-card", "colour-slots", "colour-actions", "colour-sequence-toggle",
    "background-row", "symmetry-card", "symmetry-options", "grid-card", "grid-settings",
    "edge-toggles", "thread-key", "colour-dialog", "thread-dialog", "lines-dialog",  # chunk 5
]


@pytest.mark.parametrize("width", [1280, 390])
def test_layout_regions_and_no_sideways_scroll(context: Any, site_url: str, width: int) -> None:
    page = context.new_page()
    try:
        page.set_viewport_size({"width": width, "height": 860})
        app = App(page, site_url).load()
        for element_id in OWNED_CONTAINERS:
            assert page.locator(f"#{element_id}").count() == 1, element_id
        assert page.evaluate("document.documentElement.scrollWidth") <= width
        grid_box = page.locator("#grid").bounding_box()
        assert grid_box["x"] >= 0 and grid_box["x"] + grid_box["width"] <= width
        app.click_cell(0, 0)  # still usable at this width
        assert app.colour(0, 0) == RED
        assert app.errors == []
    finally:
        page.close()


# Files (chunk 6): open, save, PNG export, autosave and ?example= -------------

EXAMPLE = ROOT / "examples" / "flower-band.json"


@pytest.fixture
def file_page(context: Any, site_url: str) -> Iterator[Any]:
    page = context.new_page()
    page.goto(site_url + "i18n/nb.json")
    page.evaluate("localStorage.clear()")
    # Accept "unsaved changes" questions (confirm and beforeunload).
    page.on("dialog", lambda dialog: dialog.accept())
    yield page
    page.close()


def start(page: Any, url: str) -> App:
    app = App(page, url)
    page.goto(url)
    page.wait_for_function("window.kvaleReady === true", timeout=BOOT_TIMEOUT_MS)
    return app


def wait_dirty(page: Any, dirty: bool) -> None:
    value = "true" if dirty else "false"
    page.wait_for_function(f"document.getElementById('doc-info').dataset.dirty === '{value}'")


def wait_name(page: Any, name: str) -> None:
    page.wait_for_function(f"document.getElementById('doc-name').textContent === {name!r}")


def preview_matches(app: App, document_path: Path) -> None:
    from kvale.core import build_colour_grid
    from kvale.core.serialization import load_document

    grid = build_colour_grid(load_document(document_path))
    app.page.click("#mode-preview")
    for x, y in [(0, 0), (5, 3), (17, 9), (40, 20)]:
        assert app.colour(x, y) == tuple(bytes.fromhex(grid[y][x].lstrip("#"))), (x, y)
    app.page.click("#mode-edit")


def test_file_buttons_and_doc_info(file_page: Any, site_url: str) -> None:
    page = file_page
    app = start(page, site_url)
    labels = page.locator("#file-actions .btn").all_text_contents()
    assert labels == ["Ny", "Åpne", "Lagre", "Lagre bilde"]
    assert page.is_visible("#doc-info")
    assert page.text_content("#doc-name") == "Nytt mønster"
    assert page.is_hidden("#doc-unsaved")
    app.click_cell(0, 0)
    wait_dirty(page, True)
    assert page.is_visible("#doc-unsaved")
    assert page.text_content("#autosave-note").startswith("Lagret i nettleseren kl.")
    page.keyboard.press("Control+z")  # back to the saved state
    wait_dirty(page, False)
    page.click("#lang-seg [data-lang=en]")
    wait_name(page, "New pattern")
    assert app.errors == []


def test_open_via_file_input_and_save_round_trip(file_page: Any, site_url: str) -> None:
    from kvale.core.serialization import load_document
    from kvale_web.files.logic import parse_document

    page = file_page
    app = start(page, site_url)
    page.set_input_files("#file-input", str(EXAMPLE))
    wait_name(page, "flower-band.json")
    assert page.is_disabled("#undo")
    preview_matches(app, EXAMPLE)

    app.click_cell(0, 0, button="right")
    app.click_cell(0, 0)
    wait_dirty(page, True)
    with page.expect_download() as info:
        page.keyboard.press("Control+s")
    download = info.value
    assert download.suggested_filename == "flower-band.json"
    saved = parse_document(Path(download.path()).read_text("utf-8"))
    expected = load_document(EXAMPLE)
    expected.erase_mark(0, 0)
    expected.set_mark(0, 0, 0)
    assert saved.to_dict() == expected.to_dict()
    wait_dirty(page, False)
    assert app.errors == []


def test_open_bad_file_shows_a_message(file_page: Any, site_url: str) -> None:
    import json

    page = file_page
    app = start(page, site_url)
    bad = {"name": "bad.json", "mimeType": "application/json", "buffer": b"nope"}
    page.set_input_files("#file-input", files=[bad])
    page.wait_for_selector("#toast:not([hidden])")
    assert page.text_content("#toast-message") == "Denne filen er ikke et Kvale-mønster."
    newer = json.dumps({"palette_sequences": [["#fff"]], "format_version": 99}).encode()
    page.set_input_files(
        "#file-input", files=[{"name": "new.json", "mimeType": "application/json", "buffer": newer}]
    )
    page.wait_for_function(
        "document.getElementById('toast-message').textContent.startsWith('Mønsteret er laget')"
    )
    assert page.text_content("#doc-name") == "Nytt mønster"
    assert app.errors == []


def test_new_asks_first_then_clears(file_page: Any, site_url: str) -> None:
    page = file_page
    app = start(page, site_url)
    asked: list[str] = []
    page.on("dialog", lambda dialog: asked.append(dialog.type))
    page.click("#file-new")  # nothing to lose: no question
    assert asked == []
    app.click_cell(2, 2)
    wait_dirty(page, True)
    page.click("#file-new")
    wait_dirty(page, False)
    assert asked == ["confirm"]
    assert app.colour(2, 2) == WHITE
    assert page.is_disabled("#undo")
    assert app.errors == []


def test_png_export(file_page: Any, site_url: str) -> None:
    import io

    from PIL import Image

    from kvale.core import build_colour_grid
    from kvale.core.serialization import load_document

    page = file_page
    app = start(page, site_url)
    page.set_input_files("#file-input", str(EXAMPLE))
    wait_name(page, "flower-band.json")
    with page.expect_download(timeout=BOOT_TIMEOUT_MS) as info:
        page.click("#file-export")
    download = info.value
    assert download.suggested_filename == "flower-band.png"
    data = Path(download.path()).read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    image = Image.open(io.BytesIO(data)).convert("RGB")
    grid = build_colour_grid(load_document(EXAMPLE))
    assert image.size == (len(grid[0]) * 16, len(grid) * 16)
    assert image.getpixel((5 * 16 + 8, 3 * 16 + 8)) == tuple(bytes.fromhex(grid[3][5].lstrip("#")))
    page.wait_for_function("!document.getElementById('file-export').disabled")
    assert page.text_content("#file-export") == "Lagre bilde"
    assert app.errors == []


def test_autosave_restores_after_reload(file_page: Any, site_url: str) -> None:
    page = file_page
    app = start(page, site_url)
    app.click_cell(3, 4)
    page.wait_for_function("(localStorage.getItem('kvale-autosave') || '').includes('\"x\":3')")
    app = start(page, site_url)  # reload
    assert app.colour(3, 4) == RED
    assert page.is_disabled("#undo")  # a fresh history
    assert page.get_attribute("#doc-info", "data-dirty") == "true"  # still not in a file
    assert page.is_visible("#autosave-note")
    assert app.errors == []


def test_example_from_url(file_page: Any, site_url: str) -> None:
    page = file_page
    app = start(page, site_url + "?example=flower-band")
    assert page.text_content("#doc-name") == "flower-band.json"
    assert page.get_attribute("#doc-info", "data-dirty") == "false"
    assert "example" not in page.url  # a reload restores the autosave instead
    preview_matches(app, EXAMPLE)
    assert app.errors == []


def test_data_link_and_missing_example(file_page: Any, site_url: str) -> None:
    from kvale_web.files.logic import encode_data_hash

    page = file_page
    app = start(page, site_url + "#" + encode_data_hash(EXAMPLE.read_text("utf-8")))
    preview_matches(app, EXAMPLE)
    assert page.text_content("#doc-name") == "Nytt mønster"

    page.evaluate("localStorage.clear()")
    app = start(page, site_url + "?example=no-such-example")
    assert page.text_content("#toast-message") == "Fant ikke mønsteret i lenken."
    # The failed fetch is the one console error expected.
    assert all("404" in error or "no-such-example" in error for error in app.errors)
