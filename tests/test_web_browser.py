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
    app.page.click("#colour-slots .slot:nth-child(1) .slot-select")  # choosing a colour leaves the eraser
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
    assert page.get_attribute(".slot:nth-child(1) .slot-edit", "aria-label") == "Modifica il colore 1"
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


# Side panels and their dialogs (chunk 5) ---------------------------------

expect = sync_api.expect  # waits, unlike a plain read: dialogs apply on their "close" event


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
    assert (data["unit_width"], data["unit_height"], data["repeats_x"], data["repeats_y"]) == (13, 12, 100, 1)

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
