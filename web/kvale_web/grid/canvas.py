"""The drawing grid on ``<canvas id="grid">``: the edit view and the whole band.

Edit view (mode ``"edit"``): the unit, an end piece or a corner (see
``scene.build_edit_scene``). In the unit only the minimal cell
(``AppState.editable_cells``) can be stitched: the rest is dimmed, the minimal
cell is outlined and ``#minimal-cell-hint`` is shown. An end piece shows the
next repeat faded beside it; a corner shows its two neighbouring ends.

Whole band (mode ``"preview"``): ``renderer.build_colour_grid`` and
``build_backstitch_segments``, drawn with one ``putImageData``.

Drawing is in two layers so the pointer stays quick on large grids: the scene
is drawn once per change into an offscreen canvas (``base``), and hover, the
backstitch rubber band and the ruler highlight are drawn over a copy of it
(``compose``).

Pointer input: click, drag and touch stitch; right-click or the unpick tool
unpicks. The backstitch tool joins intersections and carries on from the last
point (``scene.BackstitchChain``) until Esc, a click on the last point, or
another tool or target.

After each render the canvas carries ``data-redraw-ms``, ``data-cell-size``,
``data-origin-x`` and ``data-origin-y`` (CSS pixels of cell (0, 0) of the unit,
or of the band in the whole-band view) so tests can find cells.
"""

from __future__ import annotations

import math
import time
from typing import Any

import js
from pyscript import document, window

from kvale_web.dom import Bindings, Element, by_id
from kvale_web.grid import paint
from kvale_web.grid.rulers import Rulers
from kvale_web.grid.scene import (
    BackstitchChain,
    EditScene,
    Point,
    ViewBox,
    backstitch_allowed,
    band_layout,
    build_edit_scene,
    erasable_backstitch,
    is_corner,
    nearest_point,
    parse_colour,
    path_grid,
    path_lines,
    path_outline,
    path_rects,
    sides_of,
    title_key,
)
from kvale_web.grid.zoom import ZoomControls
from kvale_web.i18n import t
from kvale_web.state import DOCUMENT, LANGUAGE, VIEW, AppState

PAD = 1  # CSS pixels around the cells
EDIT_MAX_CELL = 44
EDIT_MIN_FIT = 8
PREVIEW_MAX_CELL = 24
FOCUS = "#2f5d9e"
UNPICKED = "#b3261e"
AXIS_COLOUR = "rgba(158, 27, 44, 0.6)"
EXTRA_LINE = "rgba(47, 93, 158, 0.8)"
FADE_ALPHA = 0.62

Cell = tuple[int, int]


class GridView:
    def __init__(self, state: AppState, canvas: Element, zoom: ZoomControls, rulers: Rulers) -> None:
        self.state = state
        self.canvas = canvas
        self.zoom = zoom
        self.rulers = rulers
        self.ctx = canvas.getContext("2d")
        self.base = document.createElement("canvas")
        self.base_ctx = self.base.getContext("2d")
        self.layout = by_id("edit-layout")
        self.editor = by_id("editor")
        self.hint = by_id("minimal-cell-hint")
        # Geometry of the last render, in CSS pixels.
        self.cell_size = 24
        self.box: ViewBox | None = None
        self.scene: EditScene | None = None
        self.hover: Cell | None = None
        self.snap: Point | None = None
        self.chain = BackstitchChain()
        self._chain_context: tuple[str, str] = (state.tool, state.edit_target)
        self._drag_action: str | None = None
        self._last_cell: Cell | None = None

        self.bindings = Bindings()
        self.bindings.on(canvas, "pointerdown", self.on_pointer_down)
        self.bindings.on(canvas, "pointermove", self.on_pointer_move)
        self.bindings.on(canvas, "pointerup", self.on_pointer_up)
        self.bindings.on(canvas, "pointercancel", self.on_pointer_up)
        self.bindings.on(canvas, "pointerleave", self.on_pointer_leave)
        self.bindings.on(canvas, "contextmenu", lambda event: event.preventDefault())
        self.bindings.on(window, "resize", lambda _event: self.render())
        # Esc stops a backstitch chain. Not a registered shortcut: that would
        # also stop Esc from closing dialogs.
        self.bindings.on(document, "keydown", self.on_key)
        zoom.listeners.append(self.render)
        rulers.on_highlight = self.compose
        state.subscribe(self._on_change, DOCUMENT, VIEW, LANGUAGE)

    def _on_change(self, topic: str) -> None:
        state = self.state
        context = (state.tool, state.edit_target)
        if context != self._chain_context or state.tool != "back" or state.mode != "edit":
            self._chain_context = context
            self.chain.stop()
        if topic == VIEW and state.mode != "edit":
            self.hover = self.snap = None
        self.render()
        pending = self.chain.pending
        if pending is not None and (self.box is None or not self.box.point_allowed(*pending)):
            self.chain.stop()
            self.compose()

    # Rendering -----------------------------------------------------------

    def render(self) -> None:
        start = time.perf_counter()
        if self.state.mode == "edit":
            self._render_edit()
        else:
            self._render_preview()
        self.compose()
        self.canvas.dataset.redrawMs = f"{(time.perf_counter() - start) * 1000:.2f}"

    def _available_width(self) -> float:
        """Width of the grid's column in the edit layout (it ignores its content)."""
        columns = str(window.getComputedStyle(self.layout).gridTemplateColumns).split()
        try:
            return float(columns[0].removesuffix("px"))
        except (IndexError, ValueError):
            return float(self.layout.clientWidth)

    def _ruler_size(self) -> float:
        value = str(window.getComputedStyle(self.editor).getPropertyValue("--ruler")).strip()
        try:
            return float(value.removesuffix("px") or 0)
        except ValueError:
            return 0.0

    def _size(self, columns: int, rows: int, cell: int) -> None:
        """Size the canvas and the offscreen copy for ``columns`` x ``rows`` cells."""
        self.cell_size = cell
        css_width, css_height = columns * cell + 2 * PAD, rows * cell + 2 * PAD
        paint.size_canvas(self.canvas, css_width, css_height)
        self.base_ctx = paint.size_canvas(self.base, css_width, css_height)

    def _render_edit(self) -> None:
        state = self.state
        doc = state.document
        target = state.edit_target
        dim = parse_colour(paint.token("--text-muted", "#635a50"), (0x63, 0x5A, 0x50))
        scene = build_edit_scene(doc, target, dim)
        box = scene.box
        self.scene, self.box = scene, box

        ruler = self._ruler_size()
        avail_w = max(120.0, self._available_width() - ruler - 4)
        avail_h = max(260.0, float(window.innerHeight) - (300 if target == "unit" else 400))
        fit = max(EDIT_MIN_FIT, min(EDIT_MAX_CELL, int(avail_w // box.columns), int(avail_h // box.rows)))
        cell = paint.clamp_cell(max(6, round(fit * self.zoom.level)), box.columns, box.rows)
        self._size(box.columns, box.rows, cell)
        ctx = self.base_ctx
        size = cell

        def px(x: float) -> float:
            return PAD + (x - box.x0) * size

        def py(y: float) -> float:
            return PAD + (y - box.y0) * size

        paint.put_cells(ctx, scene.pixels, box.columns, box.rows, PAD, PAD, size)
        paint.stroke(ctx, path_grid(box.columns, box.rows, size, PAD, PAD), paint.token("--cloth-line", "rgba(70,50,30,.16)"), 1)

        unit_left, unit_top = px(0), py(0)
        unit_w, unit_h = doc.unit_width * size, doc.unit_height * size
        canvas_w, canvas_h = box.columns * size + 2 * PAD, box.rows * size + 2 * PAD
        line_width = max(2.0, size / 6)
        piece_rect = (px(box.ex0), py(box.ey0), (box.ex1 - box.ex0 + 1) * size, (box.ey1 - box.ey0 + 1) * size)
        outside = path_rects([(0, 0, canvas_w, canvas_h), piece_rect])

        # Neighbours' backstitches, only in the faded part.
        if target != "unit" and scene.neighbour_stitches:
            ctx.save()
            ctx.clip(js.Path2D.new(outside), "evenodd")
            self._stitches(ctx, scene.neighbour_stitches, px, py, line_width)
            ctx.restore()

        # Symmetry axes, dashed, inside the unit.
        axes = []
        symmetry = set(doc.symmetry)
        if "mirror_x" in symmetry:
            axes.append((unit_left + unit_w / 2, unit_top, unit_left + unit_w / 2, unit_top + unit_h))
        if "mirror_y" in symmetry:
            axes.append((unit_left, unit_top + unit_h / 2, unit_left + unit_w, unit_top + unit_h / 2))
        if "diag_main" in symmetry:
            axes.append((unit_left, unit_top, unit_left + unit_w, unit_top + unit_h))
        if "diag_anti" in symmetry:
            axes.append((unit_left + unit_w, unit_top, unit_left, unit_top + unit_h))
        paint.stroke(ctx, path_lines(axes), AXIS_COLOUR, 1.5, dash=(6, 5))

        if scene.restricted:
            paint.stroke(ctx, path_outline(scene.editable, size, PAD, PAD), paint.token("--accent", "#9e1b2c"), 3, cap="square")

        # Markers: stitches you made (unit) or added here (end piece): an inset box.
        inset = max(3.0, size * 0.17)
        border = max(1.5, size * 0.08)
        by_colour: dict[str, list[tuple[float, float, float, float]]] = {}
        for x, y, colour in scene.markers:
            by_colour.setdefault(colour, []).append((px(x) + inset, py(y) + inset, size - 2 * inset, size - 2 * inset))
        for colour, rects in by_colour.items():
            paint.stroke(ctx, path_rects(rects), colour, border)
        # Unpicked here: a red cross.
        gap = size * 0.22
        crosses = []
        for x, y in scene.hidden:
            left, top = px(x), py(y)
            crosses.append((left + gap, top + gap, left + size - gap, top + size - gap))
            crosses.append((left + size - gap, top + gap, left + gap, top + size - gap))
        paint.stroke(ctx, path_lines(crosses), UNPICKED, border, cap="round")

        self._stitches(ctx, scene.stitches, px, py, line_width)

        if target != "unit":
            paint.fill(ctx, outside, paint.token("--stage", "#e8e0d2"), alpha=FADE_ALPHA, evenodd=True)
            fx, fy, fw, fh = piece_rect
            paint.stroke(ctx, path_rects([(fx + 1.5, fy + 1.5, fw - 3, fh - 3)]), paint.token("--accent", "#9e1b2c"), 3)
            if scene.has_extension:
                paint.stroke(
                    ctx, path_rects([(unit_left + 0.75, unit_top + 0.75, unit_w - 1.5, unit_h - 1.5)]),
                    EXTRA_LINE, 1.5, dash=(5, 4),
                )
            self._label_neighbours(ctx, box, piece_rect, canvas_w, canvas_h)

        self.hint.hidden = not scene.restricted
        dataset = self.canvas.dataset
        dataset.cellSize = str(size)
        dataset.originX = str(px(0))
        dataset.originY = str(py(0))
        dataset.target = target
        self.rulers.update(box, size, PAD)

    def _stitches(self, ctx: Any, stitches: list[Any], px: Any, py: Any, width: float) -> None:
        groups: dict[tuple[str, bool], list[tuple[float, float, float, float]]] = {}
        for item in stitches:
            colour = UNPICKED if item.hidden else item.colour
            groups.setdefault((colour, item.hidden), []).append((px(item.x1), py(item.y1), px(item.x2), py(item.y2)))
        for (colour, hidden), lines in groups.items():
            paint.stroke(ctx, path_lines(lines), colour, width, cap="round", dash=(4, 4) if hidden else ())

    def _label_neighbours(self, ctx: Any, box: ViewBox, piece: tuple[float, float, float, float], width: float, height: float) -> None:
        target = self.state.edit_target
        x, y, w, h = piece
        horizontal = next((e for e in sides_of(target) if e in ("left", "right")), None)
        vertical = next((e for e in sides_of(target) if e in ("top", "bottom")), None)
        mid_x = (x + w + width) / 2 if horizontal == "left" else x / 2
        mid_y = (y + h + height) / 2 if vertical == "top" else y / 2
        if not is_corner(target):
            paint.pill(ctx, t("canvas.neighbour"), mid_x if horizontal else width / 2, mid_y if vertical else height / 2)
        elif horizontal and vertical:
            paint.pill(ctx, t(title_key(vertical)), mid_x, y + h / 2)
            paint.pill(ctx, t(title_key(horizontal)), x + w / 2, mid_y)

    def _render_preview(self) -> None:
        doc = self.state.document
        layout = band_layout(doc)
        avail = max(120.0, self._available_width() - 8)
        fit = max(2, min(PREVIEW_MAX_CELL, int(avail // max(1, layout.width))))
        cell = paint.clamp_cell(max(2, round(fit * self.zoom.level)), layout.width, layout.height)
        self._size(layout.width, layout.height, cell)
        paint.draw_band(self.base_ctx, doc, cell, PAD, PAD)
        self.box = None
        self.scene = None
        self.hint.hidden = True
        self.rulers.clear()
        dataset = self.canvas.dataset
        dataset.cellSize = str(cell)
        dataset.originX = str(PAD)
        dataset.originY = str(PAD)
        dataset.target = "band"
        dataset.bandWidth = str(layout.width)
        dataset.bandHeight = str(layout.height)

    def compose(self) -> None:
        """Copy the drawn scene to the screen and draw the pointer feedback over it."""
        ctx = self.ctx
        ctx.setTransform(1, 0, 0, 1, 0, 0)
        ctx.clearRect(0, 0, self.canvas.width, self.canvas.height)
        ctx.drawImage(self.base, 0, 0)
        box = self.box
        if box is None or self.state.mode != "edit":
            return
        ratio = paint.device_ratio()
        ctx.setTransform(ratio, 0, 0, ratio, 0, 0)
        size = self.cell_size

        def px(x: float) -> float:
            return PAD + (x - box.x0) * size

        def py(y: float) -> float:
            return PAD + (y - box.y0) * size

        highlight = self.rulers.highlight
        if highlight is not None and self.state.edit_target == "unit":
            width, height = float(box.columns * size), float(box.rows * size)
            rects: list[tuple[float, float, float, float]]
            if highlight.insertion:
                rects = [(px(c) - 2, PAD, 4, height) for c in highlight.columns]
                rects += [(PAD, py(r) - 2, width, 4) for r in highlight.rows]
                paint.fill(ctx, path_rects(rects), "rgba(47, 93, 158, 0.9)")
            else:
                rects = [(px(c), PAD, size, height) for c in highlight.columns]
                rects += [(PAD, py(r), width, size) for r in highlight.rows]
                paint.fill(ctx, path_rects(rects), "rgba(47, 93, 158, 0.18)")

        if self.state.tool == "back":
            palette = self.state.document.palette
            colour = palette[self.state.active_slot % len(palette)]
            pending, snap = self.chain.pending, self.snap
            if pending is not None and snap is not None and snap != pending:
                ok = backstitch_allowed(self.state.document, self.state.edit_target, pending, snap)
                paint.stroke(
                    ctx, path_lines([(px(pending[0]), py(pending[1]), px(snap[0]), py(snap[1]))]),
                    colour if ok else paint.token("--text-muted", "#635a50"),
                    max(2.0, size / 6), dash=(6, 4), cap="round",
                )
            radius = max(4.0, size * 0.16)
            for point, filled in ((pending, True), (snap, False)):
                if point is None:
                    continue
                ctx.beginPath()
                ctx.arc(px(point[0]), py(point[1]), radius, 0, 2 * math.pi)
                ctx.fillStyle = colour if filled else "#ffffff"
                ctx.strokeStyle = FOCUS
                ctx.lineWidth = 2
                ctx.fill()
                ctx.stroke()
        elif self.hover is not None:
            hx, hy = self.hover
            paint.stroke(ctx, path_rects([(px(hx) + 1, py(hy) + 1, size - 2, size - 2)]), "rgba(47, 93, 158, 0.9)", 2)
        self.canvas.dataset.pending = "" if self.chain.pending is None else f"{self.chain.pending[0]},{self.chain.pending[1]}"

    # Pointer input -------------------------------------------------------

    def position(self, event: Any) -> tuple[float, float] | None:
        """Pointer position in cells (unit coordinates), or None outside the edit view."""
        box = self.box
        if box is None:
            return None
        rect = self.canvas.getBoundingClientRect()
        fx = (float(event.clientX - rect.left) - PAD) / self.cell_size + box.x0
        fy = (float(event.clientY - rect.top) - PAD) / self.cell_size + box.y0
        return fx, fy

    def _apply(self, cell: Cell, action: str) -> None:
        # The state ignores cells outside the minimal cell, and core ignores
        # cells outside an end piece.
        if action == "erase":
            self.state.erase_cell(*cell)
        else:
            self.state.paint_cell(*cell)

    def on_key(self, event: Any) -> None:
        if str(event.key) == "Escape" and self.chain.stop():
            self.compose()

    def on_pointer_down(self, event: Any) -> None:
        state = self.state
        box = self.box
        found = self.position(event)
        if state.mode != "edit" or box is None or found is None:
            return
        event.preventDefault()
        fx, fy = found
        target = state.edit_target
        right = event.button == 2
        if state.tool == "back" and not right:
            point = nearest_point(fx, fy)
            if not box.point_allowed(*point):
                return
            doc = state.document
            line = self.chain.click(point, lambda a, b: backstitch_allowed(doc, target, a, b))
            if line is not None:
                start, end = line
                slot = state.active_slot
                state.edit(lambda editor: editor.add_backstitch(start, end, slot, target))
            self.snap = point
            self.compose()
            return
        if state.tool == "back" or (state.tool == "unpick" and erasable_backstitch(state.document, target, fx, fy)):
            # Right-click with the backstitch tool, or unpick on a line: remove the line.
            self.chain.stop()
            if erasable_backstitch(state.document, target, fx, fy) is not None:
                state.edit(lambda editor: editor.erase_backstitch_near(fx, fy, target))
            self.compose()
            return
        cell = (math.floor(fx), math.floor(fy))
        if not box.editable(*cell):
            return
        self._drag_action = "erase" if right or state.erase_tool else "paint"
        self._last_cell = cell
        self.canvas.setPointerCapture(event.pointerId)
        state.begin_stroke()
        self._apply(cell, self._drag_action)

    def on_pointer_move(self, event: Any) -> None:
        box = self.box
        found = self.position(event)
        if self.state.mode != "edit" or box is None or found is None:
            return
        fx, fy = found
        if self.state.tool == "back":
            point = nearest_point(fx, fy)
            snap = point if box.point_allowed(*point) else None
            if snap != self.snap:
                self.snap = snap
                self.compose()
            return
        cell = (math.floor(fx), math.floor(fy))
        inside = box.editable(*cell)
        if self._drag_action is not None:
            if inside and cell != self._last_cell:
                self._last_cell = cell
                self._apply(cell, self._drag_action)
            return
        self.canvas.style.cursor = "not-allowed" if box.kind_at(*cell) == "nb" else ""
        hover = cell if inside else None
        if hover != self.hover:
            self.hover = hover
            self.compose()

    def on_pointer_up(self, _event: Any) -> None:
        if self._drag_action is not None:
            self._drag_action = None
            self._last_cell = None
            self.state.end_stroke()

    def on_pointer_leave(self, _event: Any) -> None:
        if self._drag_action is not None:
            return
        if self.hover is not None or self.snap is not None:
            self.hover = self.snap = None
            self.compose()
