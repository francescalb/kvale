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
import json
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.browser

sync_api = pytest.importorskip("playwright.sync_api")
expect = sync_api.expect  # waits, unlike a plain read: dialogs apply on their "close" event

ROOT = Path(__file__).resolve().parent.parent
BOOT_TIMEOUT_MS = 120_000
RED = (0xB1, 0x17, 0x2B)  # colour slot 1 in the default palette
GREEN = (0x2D, 0x7D, 0x32)  # colour slot 2
WHITE = (0xFF, 0xFF, 0xFF)  # default background
GREY = (0x63, 0x5A, 0x50)  # --text-muted (light), laid over cells outside the minimal cell
DIM_ALPHA = 0.2  # kvale_web.grid.canvas.DIM_ALPHA


def dimmed(colour: tuple[int, int, int]) -> tuple[int, int, int]:
    """How a cell colour looks outside the minimal cell."""
    r, g, b = (
        round(c * (1 - DIM_ALPHA) + bg * DIM_ALPHA) for c, bg in zip(colour, GREY, strict=True)
    )
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

    def cell_centre(self, x: float, y: float) -> tuple[float, float]:
        canvas = self.page.locator("#grid")
        box = canvas.bounding_box()
        size = float(canvas.get_attribute("data-cell-size"))
        origin_x = float(canvas.get_attribute("data-origin-x"))
        origin_y = float(canvas.get_attribute("data-origin-y"))
        return box["x"] + origin_x + (x + 0.5) * size, box["y"] + origin_y + (y + 0.5) * size

    def point(self, x: float, y: float) -> tuple[float, float]:
        """Page position of grid intersection (x, y) of the unit."""
        return self.cell_centre(x - 0.5, y - 0.5)

    def click_point(self, x: float, y: float, button: str = "left") -> None:
        self.page.mouse.click(*self.point(x, y), button=button)

    def pixel(self, x: float, y: float) -> tuple[int, int, int]:
        """Colour drawn at a position given in cells (cell (x, y) spans x..x+1)."""
        self.page.mouse.move(0, 0)  # remove the hover marks
        rgba = self.page.evaluate(
            """([x, y]) => {
                const canvas = document.getElementById('grid');
                const d = canvas.dataset, r = window.devicePixelRatio || 1;
                const px = (+d.originX + x * +d.cellSize) * r;
                const py = (+d.originY + y * +d.cellSize) * r;
                return Array.from(canvas.getContext('2d').getImageData(px, py, 1, 1).data);
            }""",
            [x, y],
        )
        return rgba[0], rgba[1], rgba[2]

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
    page.click("button.sym[data-op=mirror_x]")
    assert page.is_visible("#minimal-cell-hint")
    app.click_cell(1, 1)
    assert app.colour(1, 1) == RED
    assert close(app.colour(10, 1), dimmed(RED))  # generated by mirror_x, drawn dimmed

    page.click("#colour-slots .slot:nth-child(2) .slot-select")
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

    # Undoing the symmetry change switches the tile off again.
    for _ in range(4):
        page.click("#undo")
    assert page.get_attribute("button.sym[data-op=mirror_x]", "aria-pressed") == "false"
    assert page.is_disabled("#undo")
    assert page.is_hidden("#minimal-cell-hint")
    assert app.colour(10, 1) == WHITE  # the whole unit is editable again


def test_click_outside_minimal_cell_does_nothing(app: App) -> None:
    page = app.page
    page.click("button.sym[data-op=mirror_x]")
    page.click("button.sym[data-op=mirror_y]")  # minimal cell: the top-left 6x6 quarter
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
    app.page.click(
        "#colour-slots .slot:nth-child(1) .slot-select"
    )  # choosing a colour leaves the eraser
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
    assert (
        page.get_attribute(".slot:nth-child(1) .slot-edit", "aria-label") == "Modifica il colore 1"
    )
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


def test_tool_hint(app: App) -> None:
    page = app.page
    assert page.text_content("#canvas-hint").startswith("Trykk eller dra")
    assert page.is_enabled("#tool-back")
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
    "doc-info",
    "file-actions",  # chunk 6
    "tool-seg",
    "zoom-controls",
    "target-bar",
    "target-seg",
    "corner-seg",
    "end-panel",
    "ruler-top",
    "ruler-left",
    "grid",
    "edge-popover",
    "legend",
    "canvas-hint",
    "mini-band",
    "preview-caption",
    "reset-dialog",  # chunk 4
    "colours-card",
    "colour-slots",
    "colour-actions",
    "colour-sequence-toggle",
    "background-row",
    "symmetry-card",
    "symmetry-options",
    "grid-card",
    "grid-settings",
    "edge-toggles",
    "thread-key",
    "colour-dialog",
    "thread-dialog",
    "lines-dialog",  # chunk 5
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


# Chunk 4: backstitch, end pieces, corners, rulers, preview -----------------------


def test_backstitch_chains_and_stops(app: App) -> None:
    page = app.page
    page.click("#tool-back")
    assert page.get_attribute("#tool-back", "aria-pressed") == "true"
    app.click_point(1, 1)
    assert page.get_attribute("#grid", "data-pending") == "1,1"
    app.click_point(3, 1)
    app.click_point(3, 3)  # carries on from (3, 1)
    assert page.get_attribute("#grid", "data-pending") == "3,3"
    assert close(app.pixel(2, 1), RED)  # on the first line
    assert close(app.pixel(3, 2), RED)  # on the second
    assert app.pixel(2.5, 2.5) == WHITE  # no line straight from (1, 1) to (3, 3)

    page.keyboard.press("Escape")  # Esc stops the chain
    assert page.get_attribute("#grid", "data-pending") == ""
    app.click_point(5, 5)
    app.click_point(5, 5)  # the last point again stops it too
    assert page.get_attribute("#grid", "data-pending") == ""
    app.click_point(6, 6)
    page.click("#tool-cross")  # so does another tool
    page.click("#tool-back")
    assert page.get_attribute("#grid", "data-pending") == ""

    app.click_point(2, 1, button="right")  # right-click removes the line under it
    assert not close(app.pixel(2, 1), RED)
    assert close(app.pixel(3, 2), RED)
    page.keyboard.press("Control+z")
    assert close(app.pixel(2, 1), RED)
    page.click("#tool-unpick")  # unpick on a line removes it as well
    app.page.mouse.click(*app.point(3, 2))
    assert not close(app.pixel(3, 2), RED)
    page.keyboard.press("Control+z")
    page.keyboard.press("Control+z")
    page.keyboard.press("Control+z")
    assert not close(app.pixel(2, 1), RED)
    assert page.is_disabled("#undo")


def test_backstitch_only_in_the_minimal_cell(app: App) -> None:
    page = app.page
    page.click("button.sym[data-op=mirror_x]")
    page.click("#tool-back")
    app.click_point(1, 1)
    app.click_point(2, 2)
    assert page.get_attribute("#grid", "data-pending") == "2,2"
    app.click_point(11, 3)  # a line mostly outside the minimal cell: ignored
    assert page.get_attribute("#grid", "data-pending") == "2,2"
    # The line in the minimal cell is mirrored: (11, 1)-(10, 2) is its copy.
    assert close(app.pixel(10.5, 1.5), RED)
    page.click("#tool-unpick")
    page.mouse.click(*app.point(10.5, 1.5))  # a copy cannot be unpicked
    assert close(app.pixel(10.5, 1.5), RED)
    page.mouse.click(*app.point(1.5, 1.5))  # its source can, and the copy goes too
    assert not close(app.pixel(10.5, 1.5), RED)


def test_end_piece_edit_extend_reset_and_undo(app: App) -> None:
    page = app.page
    assert page.is_hidden("#end-panel")
    page.click("#target-seg [data-target=right]")
    assert page.get_attribute("#stage", "data-target") == "right"
    assert page.is_visible("#end-panel")
    assert page.text_content("#end-title") == "Høyre endestykke"
    assert page.locator("#target-seg [data-target=right] .changed").count() == 0
    assert page.locator("#legend .k-nb").count() == 1

    app.click_cell(0, 0)
    assert app.colour(0, 0) == RED
    assert page.locator("#target-seg [data-target=right] .changed").count() == 1
    page.click("#end-ext-more")
    page.click("#end-ext-more")
    assert page.input_value("#end-ext") == "2"
    assert page.text_content("#ruler-top button.extra") == "+1"
    app.click_cell(13, 0)  # in the second extra column
    assert app.colour(13, 0) == RED
    app.click_cell(-2, 0)  # the faded neighbour: nothing happens
    assert page.text_content("#end-summary").startswith("Lagt til: 2")

    page.click("#end-reset")
    assert page.is_visible("#reset-dialog")
    assert "Høyre endestykke" in page.text_content("#reset-what")
    assert page.locator("#reset-loss li").count() == 2  # stitch changes, extra columns
    page.click("#reset-cancel")
    assert page.is_hidden("#reset-dialog")
    assert page.input_value("#end-ext") == "2"

    page.click("#end-reset")
    page.click("#reset-ok")
    assert page.is_hidden("#reset-dialog")
    # The reset is applied on the dialog's "close" event, which can come a moment later.
    expect(page.locator("#end-ext")).to_have_value("0")
    assert page.locator("#target-seg [data-target=right] .changed").count() == 0
    assert page.text_content("#toast-message") == "Høyre endestykke er tilbakestilt."
    assert page.is_disabled("#end-reset")

    page.click("#undo")  # undo brings the end back
    assert page.input_value("#end-ext") == "2"
    assert app.colour(13, 0) == RED
    assert page.locator("#target-seg [data-target=right] .changed").count() == 1

    page.click("#end-done")
    assert page.get_attribute("#stage", "data-target") == "unit"
    assert page.is_hidden("#end-panel")
    assert app.colour(0, 0) == WHITE  # the unit itself was never changed


def test_corner_edit_and_mini_band(app: App) -> None:
    page = app.page
    page.click("#corner-seg [data-target=top_left]")
    assert page.get_attribute("#stage", "data-target") == "top_left"
    assert page.text_content("#end-title") == "Hjørne oppe til venstre"
    assert page.is_hidden("#end-ext-wrap")  # a corner has no size of its own
    assert page.is_visible("#corner-size")
    app.click_cell(2, 2)
    assert app.colour(2, 2) == RED
    assert page.locator("#corner-seg [data-target=top_left] .changed").count() == 1
    assert page.locator("#target-seg .changed").count() == 0
    app.click_cell(8, 8)  # the faded ends beside it are for reference only
    assert page.locator("#corner-seg .changed").count() == 1

    page.click("#end-done")
    # The mini band: click its bottom-right corner to edit that corner.
    mini = page.locator("#mini-canvas")
    mini.scroll_into_view_if_needed()
    box = mini.bounding_box()
    mini.click(position={"x": box["width"] - 3, "y": box["height"] - 3})
    assert page.get_attribute("#stage", "data-target") == "bottom_right"


def test_ruler_popover_adds_and_removes_rows(app: App) -> None:
    page = app.page
    assert page.locator("#ruler-left button").count() == 12
    page.click("button.sym[data-op=mirror_y]")
    page.click("#ruler-left [data-index='2']")
    assert page.is_visible("#edge-popover")
    assert page.text_content("#edge-title") == "Rad 3"
    assert page.text_content("#edge-note") == "Symmetrien tar også med rad 10."
    page.click("#edge-after")  # a new row below row 3, and its mirror image
    assert page.locator("#ruler-left button").count() == 14
    assert page.is_visible("#edge-popover")
    page.click("#edge-remove")
    page.click("#edge-remove")
    assert page.locator("#ruler-left button").count() == 10
    page.keyboard.press("Escape")
    assert page.is_hidden("#edge-popover")
    page.click("#ruler-top [data-index='0']")
    assert page.text_content("#edge-title") == "Kolonne 1"
    page.click("#edge-close")
    assert page.is_hidden("#edge-popover")
    page.keyboard.press("Control+z")
    assert page.locator("#ruler-left button").count() == 12
    page.keyboard.press("Control+z")
    assert page.locator("#ruler-left button").count() == 14


def test_whole_band_preview_with_ends_and_backstitch(app: App) -> None:
    page = app.page
    page.click("#tool-back")
    app.click_point(0, 0)
    app.click_point(1, 0)
    page.keyboard.press("Escape")
    page.click("#tool-cross")
    page.click("#target-seg [data-target=left]")
    page.click("#end-ext-more")
    app.click_cell(-1, 3)
    page.click("#mode-preview")
    assert page.is_hidden("#end-panel")
    assert page.locator("#ruler-top button").count() == 0
    assert page.text_content("#preview-caption") == "6 × 2 rapporter · 73 × 24 sting"
    assert app.colour(0, 3) == RED  # the extra column of the left end
    assert app.colour(1, 3) == WHITE
    # The backstitch, in every repeat (shifted by the extra column).
    assert close(app.pixel(1.5, 0.05), RED)
    assert close(app.pixel(13.5, 0.05), RED)
    page.click("#zoom-in")
    assert page.text_content("#zoom-label") == "125 %"
    page.click("#zoom-fit")
    assert page.text_content("#zoom-label") == "100 %"
    page.click("#mode-edit")  # back to drawing where you were
    assert page.get_attribute("#stage", "data-target") == "left"


# Side panels and their dialogs (chunk 5) ---------------------------------


def document(app: App) -> dict[str, Any]:
    """The current pattern as saved (``PatternDocument.to_dict``)."""
    run_python(
        app,
        """
import json
from pyscript import window
from kvale_web import app as kvale_app

window.kvaleDone = json.dumps(kvale_app.app.state.document.to_dict())
""",
    )
    data: dict[str, Any] = json.loads(app.page.evaluate("window.kvaleDone"))
    return data


def test_size_and_repeats(app: App) -> None:
    page = app.page
    assert page.is_visible("#grid-card")
    assert page.input_value("#grid-unit_width") == "12"
    page.click("#grid-settings [data-field=unit_width][data-step='1']")
    assert page.input_value("#grid-unit_width") == "13"
    page.fill("#grid-repeats_x", "150")
    page.press("#grid-repeats_x", "Enter")
    assert page.input_value("#grid-repeats_x") == "100"  # 1-100
    page.fill("#grid-repeats_y", "0")
    page.press("#grid-repeats_y", "Tab")
    assert page.input_value("#grid-repeats_y") == "1"
    data = document(app)
    assert (data["unit_width"], data["unit_height"], data["repeats_x"], data["repeats_y"]) == (
        13,
        12,
        100,
        1,
    )

    # The outer columns and rows: a switch each.
    page.click("#edge-list [data-edge=left]")
    assert page.get_attribute("#edge-list [data-edge=left]", "aria-checked") == "false"
    assert document(app)["repeat_left_column"] is False
    page.keyboard.press("Control+z")
    assert page.get_attribute("#edge-list [data-edge=left]", "aria-checked") == "true"
    page.keyboard.press("Control+z")
    page.keyboard.press("Control+z")
    page.keyboard.press("Control+z")
    assert page.input_value("#grid-unit_width") == "12"
    assert page.is_disabled("#undo")


def test_square_only_symmetry_is_switched_off_with_a_message(app: App) -> None:
    page = app.page
    assert page.is_hidden("#square-notice")
    page.click("button.sym[data-op=rotate_90]")
    assert page.get_attribute("button.sym[data-op=rotate_90]", "aria-pressed") == "true"
    assert page.get_attribute("button.sym[data-op=identity]", "aria-pressed") == "true"

    page.click("#grid-settings [data-field=unit_width][data-step='1']")  # 13 x 12
    assert page.is_visible("#toast")
    assert page.text_content("#toast-message").startswith("Rapporten er ikke kvadratisk lenger")
    tile = "button.sym[data-op=rotate_90]"
    assert page.is_disabled(tile)
    assert page.get_attribute(tile, "aria-pressed") == "false"
    assert "Krever kvadrat" in page.text_content(tile)
    assert page.is_visible("#square-notice")
    assert "13 × 12" in page.text_content("#square-notice-text")
    assert page.text_content("#make-square") == "Gjør rapporten 13 × 13"

    page.click("#make-square")
    assert page.is_hidden("#square-notice")
    assert not page.is_disabled(tile)
    assert page.input_value("#grid-unit_height") == "13"


def test_rows_and_columns_dialog(app: App) -> None:
    page = app.page
    page.click("#open-lines")
    assert page.is_visible("#lines-dialog")
    assert page.get_attribute("#lines-places [data-place=bottom_row]", "aria-pressed") == "true"
    assert page.text_content("#lines-effect").startswith("Legger til ny rad 13.")
    page.click("#lines-apply")
    assert page.is_hidden("#lines-dialog")
    expect(page.locator("#grid-unit_height")).to_have_value("13")

    # With mirror top-bottom, removing row 1 also removes the last row.
    page.click("button.sym[data-op=mirror_y]")
    page.click("#open-lines")
    page.click("#lines-action [data-action=remove]")
    page.click("#lines-places [data-place=top_row]")
    effect = page.text_content("#lines-effect")
    assert effect.startswith("Fjerner rad 1 og rad 13.")
    assert "Rapporten blir 12 × 11 sting." in effect
    assert "Symmetrien tar med flere" in effect
    assert page.locator("#lines-preview .line-gone").count() == 2
    page.click("#lines-apply")
    expect(page.locator("#grid-unit_height")).to_have_value("11")

    # Chunk 4's ruler popover opens the dialog on one row.
    run_python(
        app,
        """
from pyscript import window
from kvale_web.panels.lines import open_lines_dialog

open_lines_dialog("column", 4, remove=True)
window.kvaleDone = True
""",
    )
    assert page.is_visible("#lines-dialog")
    assert page.get_attribute("#lines-places [data-place=column]", "aria-pressed") == "true"
    assert page.get_attribute("#lines-action [data-action=remove]", "aria-pressed") == "true"
    assert page.input_value("#lines-number") == "5"
    page.click("#lines-cancel")
    assert page.input_value("#grid-unit_width") == "12"

    # The last row cannot be removed.
    page.fill("#grid-unit_height", "1")
    page.press("#grid-unit_height", "Enter")
    expect(page.locator("#grid-unit_height")).to_have_value("1")
    page.click("#open-lines")
    page.click("#lines-action [data-action=remove]")
    page.click("#lines-places [data-place=bottom_row]")
    assert page.is_disabled("#lines-apply")
    assert page.get_attribute("#lines-effect", "class") == "effect warn"
    assert page.text_content("#lines-effect").startswith("Det går ikke")
    page.keyboard.press("Escape")
    assert page.is_hidden("#lines-dialog")


def test_colour_sequence_editing(app: App) -> None:
    page = app.page
    page.click("#colour-slots .slot:nth-child(1) .slot-edit")
    assert page.is_visible("#colour-dialog")
    assert page.text_content("#colour-dialog-title") == "Farge 1"
    page.click("#colour-dialog-more")
    page.click("#colour-dialog-more")
    assert page.input_value("#colour-dialog-count") == "3"
    assert page.locator("#colour-dialog-parts .part").count() == 3
    page.click("#colour-dialog-parts .part:nth-child(2)")
    page.click("#colour-dialog-threads [title='DMC 321 – Red']")
    assert page.text_content("#colour-dialog-pick-label") == "Farge til del 2 – DMC 321 – Red"
    page.click("#colour-dialog-parts .part:nth-child(3)")
    page.fill("#colour-dialog-hex", "10, 20, 30")
    page.press("#colour-dialog-hex", "Enter")
    assert page.input_value("#colour-dialog-hex") == "#0a141e"
    assert page.is_visible("#colour-dialog-off-note")  # colour change is off
    page.click("#colour-dialog-ok")
    assert page.is_hidden("#colour-dialog")

    first = "#colour-slots .slot:nth-child(1)"
    expect(page.locator(f"{first} .swatchbar i")).to_have_count(3)
    assert page.text_content(f"{first} .slot-meta").startswith("3 farger som skifter")
    data = document(app)
    assert data["palette_sequences"][0] == ["#b1172b", "#c72b3b", "#0a141e"]
    assert data["palette_threads"][0] == [None, "dmc:321", None]

    page.click("#use-sequence")
    assert page.get_attribute("#use-sequence", "aria-checked") == "true"
    assert document(app)["use_palette_sequence"] is True

    # Fewer parts, then Cancel: nothing changes.
    page.click(f"{first} .slot-edit")
    page.fill("#colour-dialog-count", "1")
    page.press("#colour-dialog-count", "Enter")
    assert page.locator("#colour-dialog-parts .part").count() == 1
    page.click("#colour-dialog-cancel")
    assert page.locator(f"{first} .swatchbar i").count() == 3


def test_add_a_dmc_thread_through_the_picker(app: App) -> None:
    page = app.page
    page.click("#add-colour")
    assert page.is_visible("#thread-dialog")
    assert page.input_value("#thread-system") == "dmc"
    assert page.is_disabled("#thread-system option[value=anchor]")
    assert page.text_content("#thread-system option[value=madeira]") == "Madeira – kommer senere"
    assert page.text_content("#thread-count") == "454 farger fra DMC"
    assert page.is_disabled("#thread-choose")
    page.fill("#thread-search", "DMC 310")
    assert page.locator("#thread-list .dmc-row").count() >= 1
    page.click("#thread-list [data-code='310']")
    assert page.text_content("#thread-detail") == "DMC 310 – Black"
    page.click("#thread-choose")
    assert page.is_hidden("#thread-dialog")

    new_slot = "#colour-slots .slot:nth-child(5)"
    expect(page.locator(new_slot)).to_have_count(1)
    assert page.get_attribute(f"{new_slot} .slot-select", "aria-pressed") == "true"
    assert page.text_content(f"{new_slot} .slot-meta").startswith("DMC 310")
    data = document(app)
    assert data["palette_sequences"][4] == ["#000000"]
    assert data["palette_threads"][4] == ["dmc:310"]

    # Colour families narrow the list; "no match" says what to try.
    page.click("#add-colour")
    page.click("#thread-families [data-family=green]")
    assert page.get_attribute("#thread-families [data-family=green]", "aria-pressed") == "true"
    page.fill("#thread-search", "no such thread")
    assert page.text_content("#thread-list").startswith("Ingen treff")
    page.click("#thread-cancel")
    assert page.locator("#colour-slots .slot").count() == 5


def test_background_colour_and_thread_list(app: App) -> None:
    page = app.page
    page.fill("#background-input", "#112233")
    assert page.text_content("#background-hex") == "#112233"
    assert app.colour(5, 5) == (0x11, 0x22, 0x33)
    assert document(app)["background"] == "#112233"
    page.click("#undo")
    assert app.colour(5, 5) == WHITE
    assert page.is_disabled("#undo")  # the colour change was one step

    app.click_cell(0, 0)
    assert app.colour(0, 0) == RED
    page.click("#mode-preview")
    assert page.is_visible("#thread-key")
    assert page.locator("#thread-key li").count() == 1
    assert page.text_content("#thread-key li") == "Egen farge#b1172b"


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
    # The band on top, and the thread list under it (checked in test_png_lists_the_threads).
    assert image.width == len(grid[0]) * 16
    assert image.height > len(grid) * 16
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


# Feature check against the Tkinter app (chunk 8, docs/FEATURE_CHECK.md) ----


def test_undo_redo_keys_buttons_and_messages(app: App) -> None:
    page = app.page
    assert page.is_disabled("#undo") and page.is_disabled("#redo")
    app.click_cell(0, 0)
    app.click_cell(1, 0)
    assert page.is_enabled("#undo") and page.is_disabled("#redo")

    page.keyboard.press("Meta+z")  # Cmd+Z on a Mac
    assert app.colour(1, 0) == WHITE
    assert page.text_content("#toast-message") == "Angret."
    assert page.is_enabled("#redo")
    page.keyboard.press("Control+z")
    assert app.colour(0, 0) == WHITE
    assert page.is_disabled("#undo") and page.is_enabled("#redo")
    page.keyboard.press("Control+z")  # nothing left to undo: no change, no error
    assert page.is_disabled("#undo")

    page.keyboard.press("Control+Shift+Z")
    assert app.colour(0, 0) == RED
    assert page.text_content("#toast-message") == "Gjort om."
    assert page.is_visible("#toast-undo")  # "Undo" is offered after a redo
    page.keyboard.press("Meta+Shift+z")  # Cmd+Shift+Z
    assert app.colour(1, 0) == RED
    assert page.is_disabled("#redo")
    page.keyboard.press("Control+z")
    page.keyboard.press("Control+y")
    assert app.colour(1, 0) == RED
    page.click("#undo")
    assert page.text_content("#toast-message") == "Angret."
    page.click("#redo")
    assert page.text_content("#toast-message") == "Gjort om."
    assert page.is_disabled("#redo")


def test_shortcuts_wait_while_a_dialog_is_open(app: App) -> None:
    page = app.page
    app.click_cell(0, 0)
    page.click("#colour-slots .slot:nth-child(1) .slot-edit")
    assert page.is_visible("#colour-dialog")
    page.keyboard.press("Control+z")  # acts on the dialog, not the pattern behind it
    page.keyboard.press("p")
    page.keyboard.press("2")
    page.keyboard.press("Escape")
    assert page.is_hidden("#colour-dialog")
    assert page.get_attribute("#mode-edit", "aria-pressed") == "true"
    assert page.get_attribute("#colour-slots .slot:nth-child(1) .slot-select", "aria-pressed") == "true"
    assert app.colour(0, 0) == RED
    page.keyboard.press("Control+z")  # and work again once it is closed
    assert app.colour(0, 0) == WHITE


def test_png_lists_the_threads(file_page: Any, site_url: str) -> None:
    from PIL import Image

    from kvale.core import build_colour_grid
    from kvale.core.serialization import load_document
    from kvale_web.panels.colour_model import thread_rows

    page = file_page
    start(page, site_url)
    page.set_input_files("#file-input", str(EXAMPLE))
    wait_name(page, "flower-band.json")
    with page.expect_download(timeout=BOOT_TIMEOUT_MS) as info:
        page.click("#file-export")
    image = Image.open(info.value.path()).convert("RGB")
    document = load_document(EXAMPLE)
    band_height = len(build_colour_grid(document)) * 16
    key = image.crop((0, band_height, image.width, image.height))
    colours: list[tuple[int, Any]] = key.getcolors(1 << 20) or []
    counts = {colour: count for count, colour in colours}
    rows = thread_rows(document)
    assert rows
    for info_row in rows:
        chip = tuple(bytes.fromhex(info_row.hex_colour.lstrip("#")))
        assert counts.get(chip, 0) >= 16 * 16, info_row  # one chip per thread
    assert counts[(0xFF, 0xFF, 0xFF)] > key.width * key.height // 2  # on white
    assert len(counts) > len(rows) + 2  # and text beside the chips


def test_save_as_asks_for_a_new_file(file_page: Any, site_url: str) -> None:
    from kvale_web.files.logic import parse_document

    page = file_page
    app = start(page, site_url)
    # A stand-in for the browser's "save as" window (Chrome, Edge).
    page.evaluate(
        """() => {
            window.saved = [];
            window.showSaveFilePicker = async options => {
                window.suggested = options.suggestedName;
                return {
                    name: 'copy.json',
                    queryPermission: async () => 'granted',
                    requestPermission: async () => 'granted',
                    createWritable: async () => ({
                        write: async text => { window.saved.push(text); },
                        close: async () => {},
                    }),
                };
            };
        }"""
    )
    app.click_cell(2, 3)
    wait_dirty(page, True)
    page.keyboard.press("Control+Shift+S")
    wait_name(page, "copy.json")
    wait_dirty(page, False)
    assert page.evaluate("window.suggested") == "Nytt mønster.json"
    saved = parse_document(page.evaluate("window.saved[0]"))
    assert saved.to_dict() == app_document(app).to_dict()
    app.click_cell(4, 4)
    wait_dirty(page, True)
    page.keyboard.press("Control+s")  # later saves go to the same file
    page.wait_for_function("window.saved.length === 2")
    wait_dirty(page, False)

    # Without the picker (Firefox, Safari) "save as" downloads the file.
    page.evaluate("delete window.showSaveFilePicker")
    app.click_cell(5, 5)
    with page.expect_download() as info:
        page.keyboard.press("Control+Shift+S")
    assert info.value.suggested_filename == "copy.json"
    wait_dirty(page, False)
    tooltip = page.get_attribute("#file-save", "title")
    assert tooltip is not None and "Ctrl+Shift+S" in tooltip
    assert app.errors == []


def test_thread_picker_arrow_keys_and_enter(app: App) -> None:
    page = app.page
    page.click("#add-colour")
    page.fill("#thread-search", "DMC 31")
    page.keyboard.press("ArrowDown")  # the search box keeps the focus
    first = page.get_attribute("#thread-list .dmc-row[aria-selected=true]", "data-code")
    page.keyboard.press("ArrowDown")
    second = page.get_attribute("#thread-list .dmc-row[aria-selected=true]", "data-code")
    assert first and second and first != second
    page.keyboard.press("ArrowUp")
    assert page.get_attribute("#thread-list .dmc-row[aria-selected=true]", "data-code") == first
    assert page.evaluate("document.activeElement.id") == "thread-search"
    page.keyboard.press("Enter")
    assert page.is_hidden("#thread-dialog")
    assert page.text_content("#colour-slots .slot:nth-child(5) .slot-meta").startswith(f"DMC {first}")


def app_document(app: App) -> Any:
    """The pattern open in the page, read through its autosave."""
    from kvale_web.files.logic import read_autosave

    app.page.wait_for_function("!!localStorage.getItem('kvale-autosave')")
    app.page.wait_for_timeout(600)  # the autosave waits for the last change
    saved = read_autosave(app.page.evaluate("localStorage.getItem('kvale-autosave')"))
    assert saved is not None
    return saved.document
