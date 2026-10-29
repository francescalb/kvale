"""Canvas drawing helpers shared by the grid, the preview and the mini band.

Every Python->JS call costs time, so shapes are batched: many rectangles or
lines become one SVG path string, stroked with one ``Path2D``; cell colours
become one RGBA buffer, drawn with one ``putImageData`` and scaled up with
one ``drawImage``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import js
from pyscript import document, window

from kvale.core import PatternDocument, build_backstitch_segments, build_colour_grid
from kvale_web.grid.scene import BandLayout, band_layout, path_grid, path_lines

Context = Any  # CanvasRenderingContext2D
# Largest canvas side in device pixels; browsers refuse much bigger canvases.
MAX_CANVAS_SIDE = 16000

_scratch: Any = None


def token(name: str, fallback: str) -> str:
    """The value of a CSS custom property (design token) on the page."""
    value = str(window.getComputedStyle(document.documentElement).getPropertyValue(name))
    return value.strip() or fallback


def device_ratio() -> float:
    return float(window.devicePixelRatio or 1)


def size_canvas(canvas: Any, css_width: float, css_height: float) -> Context:
    """Give ``canvas`` this CSS size, a sharp backing store, and a context in CSS pixels."""
    ratio = device_ratio()
    canvas.style.width = f"{css_width}px"
    canvas.style.height = f"{css_height}px"
    canvas.width = max(1, round(css_width * ratio))
    canvas.height = max(1, round(css_height * ratio))
    ctx = canvas.getContext("2d")
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0)
    return ctx


def clamp_cell(cell: int, columns: int, rows: int) -> int:
    """Shrink a cell size so the canvas stays within what browsers draw."""
    limit = MAX_CANVAS_SIDE / device_ratio()
    return max(1, min(cell, int(limit // max(1, columns)), int(limit // max(1, rows))))


def rgba_bytes(grid: list[list[str]]) -> bytes:
    """Pack a grid of ``#rrggbb`` colours into RGBA bytes, row by row."""
    lookup: dict[str, bytes] = {}
    for row in grid:
        for colour in row:
            if colour not in lookup:
                lookup[colour] = bytes.fromhex(colour.lstrip("#")[:6]) + b"\xff"
    return b"".join(lookup[colour] for row in grid for colour in row)


def put_cells(ctx: Context, pixels: bytes, columns: int, rows: int, left: float, top: float, size: float) -> None:
    """Draw one pixel per cell, scaled up to ``size`` CSS pixels per cell, in a few calls."""
    global _scratch
    if not columns or not rows:
        return
    if _scratch is None:
        _scratch = document.createElement("canvas")
    array = js.Uint8ClampedArray.new(len(pixels))
    array.assign(pixels)
    _scratch.width, _scratch.height = columns, rows
    _scratch.getContext("2d").putImageData(js.ImageData.new(array, columns, rows), 0, 0)
    ctx.imageSmoothingEnabled = False
    ctx.drawImage(_scratch, left, top, columns * size, rows * size)


def stroke(
    ctx: Context,
    path: str,
    colour: str,
    width: float,
    *,
    dash: Sequence[float] = (),
    cap: str = "butt",
    alpha: float = 1.0,
) -> None:
    """Stroke an SVG path string in one go."""
    if not path:
        return
    ctx.save()
    ctx.globalAlpha = alpha
    ctx.strokeStyle = colour
    ctx.lineWidth = width
    ctx.lineCap = cap
    ctx.lineJoin = "round"
    if dash:
        ctx.setLineDash(js.Array.new(*dash))
    ctx.stroke(js.Path2D.new(path))
    ctx.restore()


def fill(ctx: Context, path: str, colour: str, *, alpha: float = 1.0, evenodd: bool = False) -> None:
    if not path:
        return
    ctx.save()
    ctx.globalAlpha = alpha
    ctx.fillStyle = colour
    if evenodd:
        ctx.fill(js.Path2D.new(path), "evenodd")
    else:
        ctx.fill(js.Path2D.new(path))
    ctx.restore()


def pill(ctx: Context, text: str, x: float, y: float) -> None:
    """A small rounded label on the canvas (names the faded neighbours)."""
    ctx.save()
    ctx.font = "700 11px " + token("--font-ui", "sans-serif")
    width = float(ctx.measureText(text).width) + 12
    ctx.fillStyle = token("--surface", "#ffffff")
    ctx.globalAlpha = 0.92
    ctx.beginPath()
    ctx.roundRect(x - width / 2, y - 9, width, 18, 9)
    ctx.fill()
    ctx.globalAlpha = 1
    ctx.fillStyle = token("--text-muted", "#635a50")
    ctx.textAlign = "center"
    ctx.textBaseline = "middle"
    ctx.fillText(text, x, y + 0.5)
    ctx.restore()


def draw_band(ctx: Context, document_: PatternDocument, cell: float, left: float, top: float) -> BandLayout:
    """The whole band (cells, repeat lines, backstitches) at ``cell`` CSS pixels per cell."""
    grid = build_colour_grid(document_)
    layout = band_layout(document_)
    rows = len(grid)
    columns = len(grid[0]) if rows else 0
    put_cells(ctx, rgba_bytes(grid), columns, rows, left, top, cell)
    if cell >= 5:
        stroke(ctx, path_grid(columns, rows, cell, left, top), token("--cloth-line", "rgba(70,50,30,.16)"), 1)
        bottom, right = top + rows * cell, left + columns * cell
        repeat_lines = [(left + x * cell + 0.5, top, left + x * cell + 0.5, bottom) for x in layout.x_offsets[1:]]
        repeat_lines += [(left, top + y * cell + 0.5, right, top + y * cell + 0.5) for y in layout.y_offsets[1:]]
        stroke(ctx, path_lines(repeat_lines), token("--cloth-line-strong", "rgba(70,50,30,.38)"), 1)
    by_colour: dict[str, list[tuple[float, float, float, float]]] = {}
    for segment in build_backstitch_segments(document_):
        by_colour.setdefault(segment.colour, []).append(
            (
                left + segment.start_x * cell,
                top + segment.start_y * cell,
                left + segment.end_x * cell,
                top + segment.end_y * cell,
            )
        )
    for colour, lines in by_colour.items():
        stroke(ctx, path_lines(lines), colour, max(1.2, cell / 5), cap="round")
    return layout
