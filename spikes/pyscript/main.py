"""Kvale PyScript spike: paint a 12x12 unit with symmetry, preview repeats, export.

Everything here runs in Pyodide on the browser main thread. The pattern logic is
the unchanged ``kvale.core`` package, copied into the virtual filesystem by the
``[files]`` table in pyscript.toml.
"""

from __future__ import annotations

import io
import json
import time

import js
from pyscript import document, fetch, window
from pyscript.ffi import create_proxy, to_js

from kvale.core.model import Mark, PatternDocument
from kvale.core.renderer import build_colour_grid, render_image
from kvale.core.symmetry import expand_marks

LANGUAGES = ("nb", "en", "it")
GRID_LINE = "#d6d3cc"
SEED_BORDER = "#1f1d1a"
HOVER_TINT = "rgba(60, 90, 160, 0.10)"

# --------------------------------------------------------------------------- state

doc = PatternDocument()
active_slot = 0
mode = "edit"  # "edit" or "preview"
lang = "nb"
strings: dict[str, str] = {}
string_cache: dict[str, dict[str, str]] = {}

canvas = document.getElementById("grid")
ctx = canvas.getContext("2d")
status_el = document.getElementById("status")

# Geometry of the last draw, used to map pointer positions to cells.
cell_size = 24
origin_x = 0
origin_y = 0

# Drag state
drag_action: str | None = None  # "paint" / "erase" while a pointer is down
last_cell: tuple[int, int] | None = None
hover_cell: tuple[int, int] | None = None


# --------------------------------------------------------------------------- i18n


async def load_language(code: str) -> None:
    global lang, strings
    if code not in string_cache:
        response = await fetch(f"i18n/{code}.json")
        string_cache[code] = await response.json()
    lang = code
    strings = string_cache[code]
    document.documentElement.lang = code
    document.getElementById("lang").value = code
    for element in document.querySelectorAll("[data-i18n]"):
        key = element.dataset.i18n
        if key in strings:
            element.textContent = strings[key]
    try:
        window.localStorage.setItem("kvale-lang", code)
    except Exception:  # storage may be blocked (private mode)
        pass


def t(key: str, **values: object) -> str:
    return strings.get(key, key).format(**values)


def set_status(text: str) -> None:
    status_el.textContent = text


# --------------------------------------------------------------------------- drawing


def fit_canvas(columns: int, rows: int, maximum: int) -> None:
    """Size the canvas backing store to its CSS box and pick a cell size."""
    global cell_size, origin_x, origin_y
    wrap = canvas.parentElement
    css_w = max(240, wrap.clientWidth)
    cell_size = max(4, min(maximum, (css_w - 2) // columns))
    css_h = rows * cell_size + 2
    ratio = window.devicePixelRatio or 1
    canvas.style.width = f"{css_w}px"
    canvas.style.height = f"{css_h}px"
    canvas.width = int(css_w * ratio)
    canvas.height = int(css_h * ratio)
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0)
    origin_x = (css_w - columns * cell_size) // 2
    origin_y = 1


def draw_grid_lines(columns: int, rows: int) -> None:
    ctx.beginPath()
    for x in range(columns + 1):
        px = origin_x + x * cell_size + 0.5
        ctx.moveTo(px, origin_y)
        ctx.lineTo(px, origin_y + rows * cell_size)
    for y in range(rows + 1):
        py = origin_y + y * cell_size + 0.5
        ctx.moveTo(origin_x, py)
        ctx.lineTo(origin_x + columns * cell_size, py)
    ctx.strokeStyle = GRID_LINE
    ctx.lineWidth = 1
    ctx.stroke()


def fill_cells(cells: dict[str, list[tuple[int, int]]]) -> None:
    """Fill cells grouped by colour (one fillStyle change per colour)."""
    for colour, positions in cells.items():
        ctx.fillStyle = colour
        for x, y in positions:
            ctx.fillRect(origin_x + x * cell_size, origin_y + y * cell_size, cell_size, cell_size)


def draw_editor() -> None:
    w, h = doc.unit_width, doc.unit_height
    fit_canvas(w, h, maximum=44)
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    ctx.fillStyle = doc.background
    ctx.fillRect(origin_x, origin_y, w * cell_size, h * cell_size)

    expanded = expand_marks(doc.motif, w, h, doc.symmetry)
    by_colour: dict[str, list[tuple[int, int]]] = {}
    for mark in expanded:
        colour = doc.palette[mark.colour_slot % len(doc.palette)]
        by_colour.setdefault(colour, []).append((mark.x, mark.y))
    fill_cells(by_colour)

    if hover_cell is not None:
        hx, hy = hover_cell
        ctx.fillStyle = HOVER_TINT
        ctx.fillRect(origin_x, origin_y + hy * cell_size, w * cell_size, cell_size)
        ctx.fillRect(origin_x + hx * cell_size, origin_y, cell_size, h * cell_size)

    draw_grid_lines(w, h)

    # Seed marks get an inset border; generated copies do not.
    inset = max(3, cell_size // 6)
    ctx.strokeStyle = SEED_BORDER
    ctx.lineWidth = 2
    for mark in doc.motif:
        ctx.strokeRect(
            origin_x + mark.x * cell_size + inset,
            origin_y + mark.y * cell_size + inset,
            cell_size - 2 * inset,
            cell_size - 2 * inset,
        )


def draw_preview() -> None:
    grid = build_colour_grid(doc)
    rows = len(grid)
    columns = len(grid[0]) if rows else 0
    fit_canvas(columns, rows, maximum=18)
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    # One fillRect per cell costs a Python->JS call each (2 s for 400k cells), so
    # build an RGBA buffer in Python, hand it over once, and let the canvas scale it.
    rgba: dict[str, bytes] = {}
    for row in grid:
        for colour in row:
            if colour not in rgba:
                value = colour.lstrip("#")
                rgba[colour] = bytes.fromhex(value[:6]) + b"\xff"
    pixels = b"".join(rgba[colour] for row in grid for colour in row)
    array = js.Uint8ClampedArray.new(len(pixels))
    array.assign(pixels)
    bitmap = document.createElement("canvas")
    bitmap.width, bitmap.height = columns, rows
    bitmap.getContext("2d").putImageData(js.ImageData.new(array, columns, rows), 0, 0)
    ctx.imageSmoothingEnabled = False
    ctx.drawImage(bitmap, origin_x, origin_y, columns * cell_size, rows * cell_size)
    if cell_size >= 5:
        draw_grid_lines(columns, rows)


def redraw(report: bool = True) -> None:
    start = time.perf_counter()
    if mode == "edit":
        draw_editor()
    else:
        draw_preview()
    elapsed = (time.perf_counter() - start) * 1000
    canvas.dataset.redrawMs = f"{elapsed:.2f}"
    if report:
        set_status(t("redraw", ms=f"{elapsed:.1f}"))


# --------------------------------------------------------------------------- editing


def find_source_mark(x: int, y: int) -> Mark | None:
    """Return the stored mark that produces cell (x, y) (same as gui/canvas.py)."""
    for mark in doc.motif:
        for generated in expand_marks([mark], doc.unit_width, doc.unit_height, doc.symmetry):
            if generated.x == x and generated.y == y:
                return mark
    return None


def cell_at(event) -> tuple[int, int] | None:
    rect = canvas.getBoundingClientRect()
    px = event.clientX - rect.left - origin_x
    py = event.clientY - rect.top - origin_y
    x, y = int(px // cell_size), int(py // cell_size)
    if px < 0 or py < 0 or not (0 <= x < doc.unit_width and 0 <= y < doc.unit_height):
        return None
    return x, y


def apply_at(cell: tuple[int, int], action: str) -> None:
    x, y = cell
    source = find_source_mark(x, y)
    if action == "erase":
        if source is not None:
            doc.erase_mark(source.x, source.y)
    elif source is not None:
        doc.set_mark(source.x, source.y, active_slot)
    else:
        doc.set_mark(x, y, active_slot)
    redraw()


def on_pointer_down(event) -> None:
    global drag_action, last_cell
    if mode != "edit":
        return
    event.preventDefault()
    cell = cell_at(event)
    if cell is None:
        return
    erase_tool = document.getElementById("erase").checked
    drag_action = "erase" if (event.button == 2 or erase_tool) else "paint"
    last_cell = cell
    canvas.setPointerCapture(event.pointerId)
    apply_at(cell, drag_action)


def on_pointer_move(event) -> None:
    global last_cell, hover_cell
    if mode != "edit":
        return
    cell = cell_at(event)
    if drag_action is not None:
        if cell is not None and cell != last_cell:
            last_cell = cell
            apply_at(cell, drag_action)
    elif cell != hover_cell:
        hover_cell = cell
        redraw(report=False)


def on_pointer_up(_event) -> None:
    global drag_action, last_cell
    drag_action = None
    last_cell = None


def on_pointer_leave(_event) -> None:
    global hover_cell
    if hover_cell is not None and drag_action is None:
        hover_cell = None
        if mode == "edit":
            redraw(report=False)


# --------------------------------------------------------------------------- controls


def build_palette() -> None:
    container = document.getElementById("palette")
    container.innerHTML = ""
    for index, colour in enumerate(doc.palette):
        button = document.createElement("button")
        button.className = "swatch" + (" active" if index == active_slot else "")
        button.style.setProperty("--swatch", colour)
        button.title = f"#{index + 1} {colour}"
        button.setAttribute("aria-label", f"#{index + 1}")
        button.textContent = str(index + 1)
        button.addEventListener("click", create_proxy(lambda _e, i=index: select_slot(i)))
        container.appendChild(button)


def select_slot(index: int) -> None:
    global active_slot
    active_slot = index
    document.getElementById("erase").checked = False
    build_palette()


def on_symmetry_change(_event=None) -> None:
    ops = ["identity"]
    for box in document.querySelectorAll("input.sym"):
        if box.checked:
            ops.append(box.value)
    doc.symmetry = ops
    redraw()


def sync_symmetry_boxes() -> None:
    for box in document.querySelectorAll("input.sym"):
        box.checked = box.value in doc.symmetry


def set_mode(new_mode: str) -> None:
    global mode, hover_cell
    mode = new_mode
    hover_cell = None
    document.getElementById("mode-edit").classList.toggle("active", mode == "edit")
    document.getElementById("mode-preview").classList.toggle("active", mode == "preview")
    canvas.classList.toggle("preview", mode == "preview")
    redraw()


def download(data: bytes, filename: str, mime: str) -> None:
    array = js.Uint8Array.new(len(data))
    array.assign(data)
    blob = js.Blob.new(to_js([array]), to_js({"type": mime}))
    url = js.URL.createObjectURL(blob)
    link = document.createElement("a")
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    js.setTimeout(create_proxy(lambda: js.URL.revokeObjectURL(url)), 1000)


def export_png(_event=None) -> None:
    buffer = io.BytesIO()
    render_image(doc, cell_size=16).save(buffer, format="PNG")
    download(buffer.getvalue(), "kvale.png", "image/png")


def save_json(_event=None) -> None:
    text = json.dumps(doc.to_dict(), indent=2)
    download(text.encode("utf-8"), "kvale.json", "application/json")


def open_json(_event=None) -> None:
    document.getElementById("file-input").click()


async def on_file_chosen(event) -> None:
    global doc, active_slot
    files = event.target.files
    if files.length == 0:
        return
    chosen = files.item(0)
    try:
        data = json.loads(await chosen.text())
        if not isinstance(data, dict):
            raise ValueError("JSON object expected")
        doc = PatternDocument.from_dict(data)
    except Exception as error:  # noqa: BLE001 - show any parse/validation problem
        set_status(t("load_error", error=error))
        return
    finally:
        event.target.value = ""
    active_slot = 0
    sync_symmetry_boxes()
    build_palette()
    redraw(report=False)
    set_status(t("loaded", name=chosen.name))


def clear(_event=None) -> None:
    doc.motif = []
    redraw()


def on_key(event) -> None:
    if event.target.tagName in ("INPUT", "SELECT", "TEXTAREA") and event.target.type != "checkbox":
        return
    key = event.key.lower()
    if event.ctrlKey or event.metaKey:
        if key == "s":
            event.preventDefault()
            save_json()
        elif key == "o":
            event.preventDefault()
            open_json()
        return
    if key == "e":
        box = document.getElementById("erase")
        box.checked = not box.checked
    elif key == "p":
        set_mode("edit" if mode == "preview" else "preview")
    elif key in "1234" and len(key) == 1:
        select_slot(int(key) - 1)


async def on_language(event) -> None:
    await load_language(event.target.value)
    redraw()


def bind(selector_or_el, event_name: str, handler) -> None:
    element = (
        document.querySelector(selector_or_el) if isinstance(selector_or_el, str) else selector_or_el
    )
    element.addEventListener(event_name, create_proxy(handler))


def kvale_bench(width: int, repeats_x: int, repeats_y: int) -> object:
    """Measurement hook for check.py: time redraws on a bigger random pattern."""
    global doc, mode
    import random

    rng = random.Random(1)
    saved_doc, saved_mode = doc, mode
    doc = PatternDocument(unit_width=width, unit_height=width, repeats_x=repeats_x,
                          repeats_y=repeats_y, symmetry=["identity", "mirror_x", "mirror_y"])
    for _ in range(width * width // 8):
        doc.set_mark(rng.randrange(width), rng.randrange(width), rng.randrange(4))
    result = {"seed_marks": len(doc.motif)}
    start = time.perf_counter()
    build_colour_grid(doc)
    result["build_colour_grid"] = round((time.perf_counter() - start) * 1000, 1)
    for name in ("edit", "preview"):
        mode = name
        redraw(report=False)
        result[f"{name}_redraw"] = float(canvas.dataset.redrawMs)
    start = time.perf_counter()
    find_source_mark(width - 1, width - 1)
    result["find_source_mark"] = round((time.perf_counter() - start) * 1000, 2)
    start = time.perf_counter()
    render_image(doc, cell_size=16).save(io.BytesIO(), format="PNG")
    result["png_export"] = round((time.perf_counter() - start) * 1000, 1)
    doc, mode = saved_doc, saved_mode
    redraw(report=False)
    return to_js(result)


# --------------------------------------------------------------------------- start-up


async def main() -> None:
    preferred = None
    try:
        preferred = window.localStorage.getItem("kvale-lang")
    except Exception:
        pass
    if preferred not in LANGUAGES:
        preferred = str(window.navigator.language or "nb")[:2]
        preferred = {"no": "nb", "nn": "nb"}.get(preferred, preferred)
    await load_language(preferred if preferred in LANGUAGES else "en")

    bind(canvas, "pointerdown", on_pointer_down)
    bind(canvas, "pointermove", on_pointer_move)
    bind(canvas, "pointerup", on_pointer_up)
    bind(canvas, "pointercancel", on_pointer_up)
    bind(canvas, "pointerleave", on_pointer_leave)
    bind(canvas, "contextmenu", lambda e: e.preventDefault())
    for box in document.querySelectorAll("input.sym"):
        bind(box, "change", on_symmetry_change)
    bind("#mode-edit", "click", lambda _e: set_mode("edit"))
    bind("#mode-preview", "click", lambda _e: set_mode("preview"))
    bind("#export-png", "click", export_png)
    bind("#save-json", "click", save_json)
    bind("#open-json", "click", open_json)
    bind("#clear", "click", clear)
    bind("#file-input", "change", on_file_chosen)
    bind("#lang", "change", on_language)
    bind(document, "keydown", on_key)
    bind(window, "resize", lambda _e: redraw(report=False))

    build_palette()
    sync_symmetry_boxes()
    redraw(report=False)
    document.body.classList.remove("booting")
    window.kvaleBench = create_proxy(kvale_bench)
    window.kvaleReady = True


await main()  # noqa: F704 - PyScript supports top-level await
