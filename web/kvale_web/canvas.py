"""The drawing grid on the ``<canvas id="grid">`` element (chunk 4 extends this).

Belongs here: drawing the editable unit and the repeat preview, pointer input
(paint, erase, drag, touch), hover effects, row/column insert/remove at the
grid edge, and zoom.

``GridView`` re-renders on the ``DOCUMENT`` and ``VIEW`` topics. All edits go
through ``AppState`` so they get undo/redo. Only the minimal cell
(``AppState.editable_cells``) can be painted: the rest of the unit is drawn
dimmed, the minimal cell gets an outline and ``#minimal-cell-hint`` is shown.
After each render the canvas carries ``data-redraw-ms``, ``data-cell-size``, ``data-origin-x`` and
``data-origin-y`` (CSS pixels) so tests can find cells.

Python->JS calls cost about a microsecond each, so avoid one call per cell for
large drawings: the preview builds one RGBA buffer and hands it over with a
single ``putImageData`` (see ``FINDINGS.md`` on the ``spike/pyscript`` branch).
"""

from __future__ import annotations

import time
from typing import Any

import js
from pyscript import document, window

from kvale.core.renderer import build_colour_grid
from kvale.core.symmetry import expand_marks
from kvale_web.dom import Bindings, Element, by_id
from kvale_web.state import DOCUMENT, VIEW, AppState

GRID_LINE = "#d6d3cc"
SEED_BORDER = "#1f1d1a"
HOVER_TINT = "rgba(60, 90, 160, 0.10)"
# Cells outside the minimal cell are greyed with the muted text colour
# (``--color-muted``) at this opacity: dimmed but still readable. The minimal
# cell is outlined in ``--color-accent``.
DIM_ALPHA = 0.2
DIM_TOKEN, DIM_FALLBACK = "--color-muted", "#6b665e"
OUTLINE_TOKEN, OUTLINE_FALLBACK = "--color-accent", "#b1172b"
EDIT_MAX_CELL = 44
PREVIEW_MAX_CELL = 18
MIN_CELL = 4

Cell = tuple[int, int]


def rgba_bytes(grid: list[list[str]]) -> bytes:
    """Pack a grid of ``#rrggbb`` colours into RGBA bytes, row by row."""
    lookup: dict[str, bytes] = {}
    for row in grid:
        for colour in row:
            if colour not in lookup:
                lookup[colour] = bytes.fromhex(colour.lstrip("#")[:6]) + b"\xff"
    return b"".join(lookup[colour] for row in grid for colour in row)


class GridView:
    def __init__(self, state: AppState, canvas: Element) -> None:
        self.state = state
        self.canvas = canvas
        self.ctx = canvas.getContext("2d")
        # Geometry of the last render, in CSS pixels.
        self.cell_size = 24
        self.origin_x = 0
        self.origin_y = 1
        self.hover: Cell | None = None
        self._drag_action: str | None = None
        self._last_cell: Cell | None = None
        self.hint = by_id("minimal-cell-hint")

        self.bindings = Bindings()
        self.bindings.on(canvas, "pointerdown", self.on_pointer_down)
        self.bindings.on(canvas, "pointermove", self.on_pointer_move)
        self.bindings.on(canvas, "pointerup", self.on_pointer_up)
        self.bindings.on(canvas, "pointercancel", self.on_pointer_up)
        self.bindings.on(canvas, "pointerleave", self.on_pointer_leave)
        self.bindings.on(canvas, "contextmenu", lambda event: event.preventDefault())
        self.bindings.on(window, "resize", lambda _event: self.render())
        state.subscribe(self._on_change, DOCUMENT, VIEW)

    def _on_change(self, topic: str) -> None:
        if topic == VIEW and self.state.mode != "edit":
            self.hover = None
        self.render()

    # Drawing -----------------------------------------------------------

    def render(self) -> None:
        start = time.perf_counter()
        restricted = False
        if self.state.mode == "edit":
            restricted = self._draw_editor()
        else:
            self._draw_preview()
        self.hint.hidden = not restricted
        dataset = self.canvas.dataset
        dataset.redrawMs = f"{(time.perf_counter() - start) * 1000:.2f}"
        dataset.cellSize = str(self.cell_size)
        dataset.originX = str(self.origin_x)
        dataset.originY = str(self.origin_y)

    def _fit(self, columns: int, rows: int, maximum: int) -> None:
        """Size the canvas backing store to its CSS box and choose a cell size."""
        css_width = max(240, int(self.canvas.parentElement.clientWidth))
        self.cell_size = max(MIN_CELL, min(maximum, (css_width - 2) // max(1, columns)))
        css_height = rows * self.cell_size + 2
        ratio = window.devicePixelRatio or 1
        self.canvas.style.width = f"{css_width}px"
        self.canvas.style.height = f"{css_height}px"
        self.canvas.width = int(css_width * ratio)
        self.canvas.height = int(css_height * ratio)
        self.ctx.setTransform(ratio, 0, 0, ratio, 0, 0)
        self.origin_x = (css_width - columns * self.cell_size) // 2
        self.origin_y = 1

    def _grid_lines(self, columns: int, rows: int) -> None:
        ctx, size = self.ctx, self.cell_size
        ctx.beginPath()
        for x in range(columns + 1):
            px = self.origin_x + x * size + 0.5
            ctx.moveTo(px, self.origin_y)
            ctx.lineTo(px, self.origin_y + rows * size)
        for y in range(rows + 1):
            py = self.origin_y + y * size + 0.5
            ctx.moveTo(self.origin_x, py)
            ctx.lineTo(self.origin_x + columns * size, py)
        ctx.strokeStyle = GRID_LINE
        ctx.lineWidth = 1
        ctx.stroke()

    def _token(self, name: str, fallback: str) -> str:
        """The value of a CSS custom property (design token) on the page."""
        value = str(window.getComputedStyle(document.documentElement).getPropertyValue(name))
        return value.strip() or fallback

    def _draw_editor(self) -> bool:
        """Draw the unit. Returns True when only a part of it (the minimal cell) is editable."""
        doc = self.state.document
        width, height = doc.unit_width, doc.unit_height
        self._fit(width, height, EDIT_MAX_CELL)
        ctx, size = self.ctx, self.cell_size
        ox, oy = self.origin_x, self.origin_y
        ctx.clearRect(0, 0, self.canvas.width, self.canvas.height)
        ctx.fillStyle = doc.background
        ctx.fillRect(ox, oy, width * size, height * size)

        # Group cells by colour: one fillStyle change per colour.
        palette = doc.palette
        by_colour: dict[str, list[Cell]] = {}
        for mark in expand_marks(doc.motif, width, height, doc.symmetry):
            colour = palette[mark.colour_slot % len(palette)]
            by_colour.setdefault(colour, []).append((mark.x, mark.y))
        for colour, cells in by_colour.items():
            ctx.fillStyle = colour
            for x, y in cells:
                ctx.fillRect(ox + x * size, oy + y * size, size, size)

        if self.hover is not None:
            hx, hy = self.hover
            ctx.fillStyle = HOVER_TINT
            ctx.fillRect(ox, oy + hy * size, width * size, size)
            ctx.fillRect(ox + hx * size, oy, size, height * size)

        editable = self.state.editable_cells
        restricted = len(editable) < width * height
        if restricted:
            ctx.globalAlpha = DIM_ALPHA
            ctx.fillStyle = self._token(DIM_TOKEN, DIM_FALLBACK)
            for y in range(height):
                for x in range(width):
                    if (x, y) not in editable:
                        ctx.fillRect(ox + x * size, oy + y * size, size, size)
            ctx.globalAlpha = 1

        self._grid_lines(width, height)
        if restricted:
            self._outline(editable)

        # Seed marks get an inset border; generated copies do not.
        inset = max(3, size // 6)
        ctx.strokeStyle = SEED_BORDER
        ctx.lineWidth = 2
        for mark in doc.motif:
            ctx.strokeRect(
                ox + mark.x * size + inset,
                oy + mark.y * size + inset,
                size - 2 * inset,
                size - 2 * inset,
            )
        return restricted

    def _outline(self, cells: frozenset[Cell]) -> None:
        """Stroke the outline of a set of cells: every cell side with no cell beyond it."""
        ctx, size = self.ctx, self.cell_size
        ox, oy = self.origin_x, self.origin_y
        ctx.beginPath()
        for x, y in cells:
            left, top = ox + x * size, oy + y * size
            if (x, y - 1) not in cells:
                ctx.moveTo(left, top)
                ctx.lineTo(left + size, top)
            if (x, y + 1) not in cells:
                ctx.moveTo(left, top + size)
                ctx.lineTo(left + size, top + size)
            if (x - 1, y) not in cells:
                ctx.moveTo(left, top)
                ctx.lineTo(left, top + size)
            if (x + 1, y) not in cells:
                ctx.moveTo(left + size, top)
                ctx.lineTo(left + size, top + size)
        ctx.strokeStyle = self._token(OUTLINE_TOKEN, OUTLINE_FALLBACK)
        ctx.lineWidth = 3
        ctx.lineCap = "square"
        ctx.stroke()

    def _draw_preview(self) -> None:
        grid = build_colour_grid(self.state.document)
        rows = len(grid)
        columns = len(grid[0]) if rows else 0
        self._fit(columns, rows, PREVIEW_MAX_CELL)
        ctx, size = self.ctx, self.cell_size
        ctx.clearRect(0, 0, self.canvas.width, self.canvas.height)
        if not columns:
            return
        # One fillRect per cell is one JS call each (2 s for 400k cells). Build
        # an RGBA buffer in Python, hand it over once, and let the canvas scale it.
        pixels = rgba_bytes(grid)
        array = js.Uint8ClampedArray.new(len(pixels))
        array.assign(pixels)
        bitmap = document.createElement("canvas")
        bitmap.width, bitmap.height = columns, rows
        bitmap.getContext("2d").putImageData(js.ImageData.new(array, columns, rows), 0, 0)
        ctx.imageSmoothingEnabled = False
        ctx.drawImage(bitmap, self.origin_x, self.origin_y, columns * size, rows * size)
        if size >= 5:
            self._grid_lines(columns, rows)

    # Pointer input -----------------------------------------------------

    def cell_at(self, event: Any) -> Cell | None:
        """The unit cell under a pointer event, or None outside the unit."""
        rect = self.canvas.getBoundingClientRect()
        px = float(event.clientX - rect.left) - self.origin_x
        py = float(event.clientY - rect.top) - self.origin_y
        if px < 0 or py < 0:
            return None
        x, y = int(px // self.cell_size), int(py // self.cell_size)
        doc = self.state.document
        if not (x < doc.unit_width and y < doc.unit_height):
            return None
        return x, y

    def _apply(self, cell: Cell, action: str) -> None:
        # Cells outside the minimal cell are ignored by the state.
        if action == "erase":
            self.state.erase_cell(*cell)
        else:
            self.state.paint_cell(*cell)

    def on_pointer_down(self, event: Any) -> None:
        if self.state.mode != "edit":
            return
        event.preventDefault()
        cell = self.cell_at(event)
        if cell is None:
            return
        erase = event.button == 2 or self.state.erase_tool
        self._drag_action = "erase" if erase else "paint"
        self._last_cell = cell
        self.canvas.setPointerCapture(event.pointerId)
        self.state.begin_stroke()
        self._apply(cell, self._drag_action)

    def on_pointer_move(self, event: Any) -> None:
        if self.state.mode != "edit":
            return
        cell = self.cell_at(event)
        if self._drag_action is not None:
            if cell is not None and cell != self._last_cell:
                self._last_cell = cell
                self._apply(cell, self._drag_action)
        elif cell != self.hover:
            self.hover = cell
            self.render()

    def on_pointer_up(self, _event: Any) -> None:
        if self._drag_action is not None:
            self._drag_action = None
            self._last_cell = None
            self.state.end_stroke()

    def on_pointer_leave(self, _event: Any) -> None:
        if self.hover is not None and self._drag_action is None:
            self.hover = None
            if self.state.mode == "edit":
                self.render()
