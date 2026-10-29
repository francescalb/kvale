"""What the drawing grid shows, as plain data (no ``js`` imports).

The canvas modules turn this into pixels. Keeping the logic here means it runs
and is tested in normal CPython (``tests/test_web_grid_scene.py``).

Coordinates are the core's: cell (0, 0) is the top-left cell of the unit, and
end pieces reach negative coordinates (top, left) or coordinates from the unit
size upwards (bottom, right). Backstitches join grid intersections.

- ``view_box``: the cells shown when editing a target, which of them can be
  edited, and the faded neighbours beside an end piece or a corner.
- ``build_edit_scene``: the cell colours (one RGBA buffer, drawn with a single
  ``putImageData``), markers and backstitches of the edit view.
- ``BackstitchChain``: the backstitch tool's "carry on from the last point".
- ``line_orbit_names`` / ``LineHighlight``: rows and columns tied by symmetry,
  for the ruler popover.
- ``reset_loss``: what resetting an end piece or a corner throws away.
- ``band_layout`` / ``region_rect`` / ``region_at``: where the unit, the ends
  and the corners lie in the whole band (the clickable mini band).
- ``path_*``: SVG path strings, so the canvas strokes many shapes in one call.
"""

from __future__ import annotations

import copy
import math
import re
from collections.abc import Callable, Collection, Iterable
from dataclasses import dataclass, field
from typing import Literal, cast

from kvale.core.editing import (
    CORNERS,
    EDGES,
    Axis,
    Corner,
    Edge,
    EditTarget,
    EndPiece,
    base_backstitches,
    base_marks,
    find_backstitch_near,
    get_end_piece,
    grid_line_orbit,
)
from kvale.core.model import CORNER_EDGES, Backstitch, BackstitchKey, PatternDocument
from kvale.core.renderer import _included_column_indices, _included_row_indices
from kvale.core.symmetry import (
    backstitch_in_minimal_cell,
    expand_backstitches,
    expand_marks,
    minimal_cell,
)

Point = tuple[int, int]
Cell = tuple[int, int]
RGB = tuple[int, int, int]
Kind = Literal["unit", "extra", "nb"]
CellState = Literal["base", "added", "hidden"]

# Short names used in i18n keys (corner.title.tl, end.title.left ...).
SHORT_NAMES: dict[EditTarget, str] = {
    "unit": "unit",
    "top": "top",
    "bottom": "bottom",
    "left": "left",
    "right": "right",
    "top_left": "tl",
    "top_right": "tr",
    "bottom_left": "bl",
    "bottom_right": "br",
}
# Largest extension (extra rows/columns) the end panel offers.
MAX_EXTENSION = 50
# Zoom steps; 1 is "fit".
ZOOM_LEVELS = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0)

# Colours of the edit view that are not design tokens (as in the mockup).
EXTRA_TINT: RGB = (47, 93, 158)
EXTRA_ALPHA = 0.10
HIDDEN_ALPHA = 0.2
DIM_ALPHA = 0.2


def is_corner(target: EditTarget) -> bool:
    return target in CORNERS


def as_edge(target: EditTarget) -> Edge | None:
    """``target`` as an edge end piece, or None for the unit or a corner."""
    for edge in EDGES:
        if edge == target:
            return edge
    return None


def sides_of(target: EditTarget) -> tuple[Edge, ...]:
    """The edges an end piece belongs to: one for an edge, two for a corner."""
    if target in CORNER_EDGES:
        row_edge, column_edge = CORNER_EDGES[target]
        return cast(Edge, row_edge), cast(Edge, column_edge)
    edge = as_edge(target)
    return () if edge is None else (edge,)


def corners_of(edge: Edge) -> tuple[Corner, ...]:
    """The two corners next to an edge."""
    return tuple(corner for corner in CORNERS if edge in CORNER_EDGES[corner])


def title_key(target: EditTarget) -> str:
    """i18n key of an end piece's or corner's title ("Left end", "Top-left corner")."""
    if target == "unit":
        return "target.unit"
    prefix = "corner.title." if is_corner(target) else "end.title."
    return prefix + SHORT_NAMES[target]


def zoom_step(level: float, direction: int) -> float:
    """The next zoom level up (direction 1) or down (-1); stays at the ends."""
    if direction > 0:
        return next((z for z in ZOOM_LEVELS if z > level + 1e-9), level)
    return next((z for z in reversed(ZOOM_LEVELS) if z < level - 1e-9), level)


# View box -------------------------------------------------------------------


@dataclass(frozen=True)
class ViewBox:
    """The cells shown (``x0..x1``, ``y0..y1``) and editable (``ex0..ey1``), inclusive."""

    target: EditTarget
    width: int  # unit size
    height: int
    x0: int
    x1: int
    y0: int
    y1: int
    ex0: int
    ex1: int
    ey0: int
    ey1: int

    @property
    def columns(self) -> int:
        return self.x1 - self.x0 + 1

    @property
    def rows(self) -> int:
        return self.y1 - self.y0 + 1

    def kind_at(self, x: int, y: int) -> Kind | None:
        """"unit" (a cell of the unit), "extra" (beyond it), "nb" (faded neighbour) or None."""
        if not (self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1):
            return None
        if self.target == "unit":
            return "unit"
        if self.ex0 <= x <= self.ex1 and self.ey0 <= y <= self.ey1:
            return "unit" if 0 <= x < self.width and 0 <= y < self.height else "extra"
        return "nb"

    def editable(self, x: int, y: int) -> bool:
        return self.ex0 <= x <= self.ex1 and self.ey0 <= y <= self.ey1

    def point_allowed(self, x: int, y: int) -> bool:
        """True when intersection (x, y) is on the editable part (a backstitch end)."""
        return self.ex0 <= x <= self.ex1 + 1 and self.ey0 <= y <= self.ey1 + 1


def neighbour_size(size: int) -> int:
    """How many cells of the neighbouring repeat are shown beside an end piece."""
    return min(size, max(3, math.ceil(size / 2)))


def view_box(document: PatternDocument, target: EditTarget) -> ViewBox:
    """The cells shown when editing ``target``.

    The unit shows itself. An end piece shows itself (unit plus extension) and
    part of the next repeat inwards, faded. A corner shows itself with both
    neighbouring end pieces faded beside it.
    """
    w, h = document.unit_width, document.unit_height
    x0, x1, y0, y1 = 0, w - 1, 0, h - 1
    ex0, ex1, ey0, ey1 = x0, x1, y0, y1
    if target != "unit":
        nbc, nbr = neighbour_size(w), neighbour_size(h)
        for edge in sides_of(target):
            ext = document.extension_of(edge)
            if edge == "left":
                ex0 = x0 = -ext
                x1 = w - 1 + nbc
            elif edge == "right":
                ex1 = x1 = w - 1 + ext
                x0 = -nbc
            elif edge == "top":
                ey0 = y0 = -ext
                y1 = h - 1 + nbr
            else:
                ey1 = y1 = h - 1 + ext
                y0 = -nbr
    return ViewBox(target, w, h, x0, x1, y0, y1, ex0, ex1, ey0, ey1)


def neighbour_source(target: EditTarget, width: int, height: int, x: int, y: int) -> tuple[EditTarget, int, int]:
    """Which piece a faded neighbour cell shows, and where in it.

    Beside an end piece: the plain unit. Beside a corner: the end piece it
    borders (or the unit, diagonally).
    """
    wx, wy = x % width, y % height
    if not is_corner(target):
        return "unit", wx, wy
    row_edge, column_edge = sides_of(target)
    across = x >= width if column_edge == "left" else x < 0
    down = y >= height if row_edge == "top" else y < 0
    if across and down:
        return "unit", wx, wy
    if across:
        return row_edge, wx, y
    return column_edge, x, wy


def neighbour_shift(target: EditTarget, width: int, height: int) -> tuple[int, int]:
    """How far the next repeat inwards is from an end piece, in cells."""
    dx = dy = 0
    for edge in sides_of(target):
        if edge == "left":
            dx = width
        elif edge == "right":
            dx = -width
        elif edge == "top":
            dy = height
        else:
            dy = -height
    return dx, dy


# Piece contents -------------------------------------------------------------


def piece_cells(document: PatternDocument, piece: EndPiece) -> dict[Cell, tuple[int, CellState]]:
    """Cells shown in an end piece or corner: position -> (colour slot, state)."""
    cells: dict[Cell, tuple[int, CellState]] = {
        position: (mark.colour_slot, "base") for position, mark in base_marks(document, piece).items()
    }
    override = get_end_piece(document, piece)
    if override is not None:
        for removed in override.removed_cells:
            position = (removed.x, removed.y)
            if position in cells:
                cells[position] = (cells[position][0], "hidden")
        for mark in override.added_marks:
            cells[(mark.x, mark.y)] = (mark.colour_slot, "added")
    return cells


def piece_backstitches(
    document: PatternDocument, piece: EndPiece
) -> dict[BackstitchKey, tuple[Backstitch, CellState]]:
    """Backstitches shown in an end piece or corner: key -> (backstitch, state)."""
    stitches: dict[BackstitchKey, tuple[Backstitch, CellState]] = {
        key: (item, "base") for key, item in base_backstitches(document, piece).items()
    }
    override = get_end_piece(document, piece)
    if override is not None:
        for key in override.removed_backstitches:
            if key in stitches:
                stitches[key] = (stitches[key][0], "hidden")
        for item in override.added_backstitches:
            stitches[item.key] = (item, "added")
    return stitches


@dataclass(frozen=True)
class PieceSummary:
    added: int = 0
    removed: int = 0
    lines: int = 0
    extension: int = 0

    @property
    def empty(self) -> bool:
        return not (self.added or self.removed or self.lines or self.extension)


def piece_summary(document: PatternDocument, piece: EndPiece) -> PieceSummary:
    """Counts of the changes an end piece or corner makes."""
    override = get_end_piece(document, piece)
    if override is None:
        return PieceSummary()
    return PieceSummary(
        added=len(override.added_marks),
        removed=len(override.removed_cells),
        lines=len(override.added_backstitches) + len(override.removed_backstitches),
        extension=override.extension,
    )


def changed_pieces(document: PatternDocument) -> frozenset[EndPiece]:
    """The end pieces and corners that change anything (they get a dot)."""
    return frozenset(piece for piece in (*EDGES, *CORNERS) if not piece_summary(document, piece).empty)


@dataclass(frozen=True)
class ResetLoss:
    """What resetting an end piece or a corner throws away."""

    summary: PieceSummary
    corner_stitches: int = 0  # stitches in the neighbouring corners' share of the extension


def reset_loss(document: PatternDocument, piece: EndPiece) -> ResetLoss:
    summary = piece_summary(document, piece)
    lost = 0
    edge = as_edge(piece)
    if edge is not None and summary.extension:
        from kvale.core.editing import reset_end_piece

        def count(doc: PatternDocument) -> int:
            total = 0
            for corner in corners_of(edge):
                override = get_end_piece(doc, corner)
                if override is not None:
                    total += len(override.added_marks) + len(override.added_backstitches)
            return total

        after = copy.deepcopy(document)
        reset_end_piece(after, piece)
        lost = count(document) - count(after)
    return ResetLoss(summary, lost)


# Edit scene -----------------------------------------------------------------


def hex_rgb(colour: str) -> RGB:
    value = colour.lstrip("#")[:6]
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    try:
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
    except ValueError:
        return 0, 0, 0


def parse_colour(value: str, fallback: RGB = (0, 0, 0)) -> RGB:
    """A CSS colour as returned by ``getComputedStyle``: ``#rgb``, ``#rrggbb`` or ``rgb(...)``."""
    value = value.strip()
    if value.startswith("#"):
        return hex_rgb(value)
    found = re.match(r"rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)", value)
    if found:
        r, g, b = (int(part) for part in found.groups())
        return r, g, b
    return fallback


def blend(below: RGB, above: RGB, alpha: float) -> RGB:
    """``above`` laid over ``below`` with opacity ``alpha``."""
    r, g, b = (round(lo * (1 - alpha) + hi * alpha) for lo, hi in zip(below, above, strict=True))
    return r, g, b


def luminance(colour: str) -> float:
    def channel(value: int) -> float:
        v = value / 255
        return v / 12.92 if v <= 0.03928 else float(((v + 0.055) / 1.055) ** 2.4)

    r, g, b = hex_rgb(colour)
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def marker_colour(colour: str) -> str:
    """Border colour of a seed/added marker on a cell of ``colour``."""
    return "#1b1712" if luminance(colour) > 0.35 else "#ffffff"


@dataclass(frozen=True)
class Stitch:
    x1: int
    y1: int
    x2: int
    y2: int
    colour: str
    hidden: bool = False


@dataclass
class EditScene:
    box: ViewBox
    pixels: bytes  # RGBA, box.columns x box.rows, row by row
    markers: list[tuple[int, int, str]] = field(default_factory=list)  # inset boxes
    hidden: list[Cell] = field(default_factory=list)  # red crosses (unpicked here)
    stitches: list[Stitch] = field(default_factory=list)
    neighbour_stitches: list[Stitch] = field(default_factory=list)  # clipped to the faded part
    restricted: bool = False  # only the minimal cell is editable
    editable: frozenset[Cell] = frozenset()
    has_extension: bool = False


def build_edit_scene(document: PatternDocument, target: EditTarget, dim: RGB = (0x63, 0x5A, 0x50)) -> EditScene:
    """Everything the edit view draws for ``target``.

    ``dim`` is the colour laid over unit cells outside the minimal cell.
    """
    box = view_box(document, target)
    w, h = document.unit_width, document.unit_height
    palette = document.palette

    def colour_of(slot: int) -> str:
        return palette[slot % len(palette)]

    background = hex_rgb(document.background)
    unit_marks = {(m.x, m.y): m.colour_slot for m in expand_marks(document.motif, w, h, document.symmetry)}
    editable = minimal_cell(w, h, document.symmetry) if target == "unit" else frozenset()
    restricted = target == "unit" and len(editable) < w * h

    scene = EditScene(box, b"", restricted=restricted, editable=editable)
    cells: dict[Cell, tuple[int, CellState]] = {}
    neighbours: dict[EditTarget, dict[Cell, tuple[int, CellState]]] = {}
    if target != "unit":
        piece: EndPiece = target
        cells = piece_cells(document, piece)
        if is_corner(target):
            for edge in sides_of(target):
                neighbours[edge] = piece_cells(document, edge)
        scene.has_extension = any(document.extension_of(edge) for edge in sides_of(target))

    rgb_cache: dict[tuple[str, int], bytes] = {}

    def pixel(colour: str | RGB, mode: int) -> bytes:
        # mode 0: plain, 1: hidden (faint), 2: dimmed (outside minimal cell), 3: extra tint
        key = (str(colour), mode)
        found = rgb_cache.get(key)
        if found is None:
            rgb = colour if isinstance(colour, tuple) else hex_rgb(colour)
            if mode == 1:
                rgb = blend(background, rgb, HIDDEN_ALPHA)
            elif mode == 2:
                rgb = blend(rgb, dim, DIM_ALPHA)
            elif mode == 3:
                rgb = blend(rgb, EXTRA_TINT, EXTRA_ALPHA)
            found = bytes((*rgb, 255))
            rgb_cache[key] = found
        return found

    plain_bg = pixel(background, 0)
    out: list[bytes] = []
    for y in range(box.y0, box.y1 + 1):
        for x in range(box.x0, box.x1 + 1):
            if target == "unit":
                slot = unit_marks.get((x, y))
                colour: str | RGB = background if slot is None else colour_of(slot)
                out.append(pixel(colour, 2) if restricted and (x, y) not in editable else (
                    plain_bg if slot is None else pixel(colour, 0)))
                continue
            kind = box.kind_at(x, y)
            if kind == "nb":
                source, sx, sy = neighbour_source(target, w, h, x, y)
                if source == "unit":
                    slot = unit_marks.get((sx, sy))
                else:
                    entry = neighbours[source].get((sx, sy))
                    slot = entry[0] if entry and entry[1] != "hidden" else None
                out.append(plain_bg if slot is None else pixel(colour_of(slot), 0))
                continue
            entry = cells.get((x, y))
            if entry is None:
                out.append(pixel(background, 3) if kind == "extra" else plain_bg)
            elif entry[1] == "hidden":
                out.append(pixel(colour_of(entry[0]), 1))
            else:
                out.append(pixel(colour_of(entry[0]), 0))
    scene.pixels = b"".join(out)

    def stitch(item: Backstitch, dx: int = 0, dy: int = 0, hidden: bool = False) -> Stitch:
        return Stitch(
            item.start_x + dx, item.start_y + dy, item.end_x + dx, item.end_y + dy,
            colour_of(item.colour_slot), hidden,
        )

    if target == "unit":
        for mark in document.motif:
            scene.markers.append((mark.x, mark.y, marker_colour(colour_of(mark.colour_slot))))
        scene.stitches = [stitch(item) for item in expand_backstitches(document.backstitches, w, h, document.symmetry)]
        return scene

    for (x, y), (slot, state) in cells.items():
        if state == "added":
            scene.markers.append((x, y, marker_colour(colour_of(slot))))
        elif state == "hidden":
            scene.hidden.append((x, y))
    piece = target
    scene.stitches = [stitch(item, hidden=state == "hidden") for item, state in piece_backstitches(document, piece).values()]

    dx, dy = neighbour_shift(target, w, h)
    unit_stitches = expand_backstitches(document.backstitches, w, h, document.symmetry)
    if not is_corner(target):
        scene.neighbour_stitches = [stitch(item, dx, dy) for item in unit_stitches]
    else:
        row_edge, column_edge = sides_of(target)
        for item, state in piece_backstitches(document, row_edge).values():
            if state != "hidden":
                scene.neighbour_stitches.append(stitch(item, dx, 0))
        for item, state in piece_backstitches(document, column_edge).values():
            if state != "hidden":
                scene.neighbour_stitches.append(stitch(item, 0, dy))
        scene.neighbour_stitches += [stitch(item, dx, dy) for item in unit_stitches]
    return scene


# Backstitch tool --------------------------------------------------------------


def nearest_point(fx: float, fy: float) -> Point:
    """The grid intersection nearest to a position given in cells."""
    return math.floor(fx + 0.5), math.floor(fy + 0.5)


def backstitch_allowed(
    document: PatternDocument, target: EditTarget, start: Point, end: Point
) -> bool:
    """Whether a backstitch from ``start`` to ``end`` may be drawn when editing ``target``.

    Both ends must lie on the editable part; in the unit with symmetry, the
    line must also lie in the minimal cell (``backstitch_in_minimal_cell``).
    """
    if start == end:
        return False
    box = view_box(document, target)
    if not (box.point_allowed(*start) and box.point_allowed(*end)):
        return False
    if target == "unit":
        cells = minimal_cell(document.unit_width, document.unit_height, document.symmetry)
        if len(cells) < document.unit_width * document.unit_height:
            return backstitch_in_minimal_cell(start, end, cells)
    return True


def erasable_backstitch(
    document: PatternDocument, target: EditTarget, fx: float, fy: float
) -> Backstitch | None:
    """The backstitch an unpick at (fx, fy) removes, or None.

    In the unit with symmetry only lines in the minimal cell can be unpicked
    (their copies follow), like cross stitches.
    """
    found = find_backstitch_near(document, fx, fy, target)
    if found is None:
        return None
    if target == "unit":
        cells = minimal_cell(document.unit_width, document.unit_height, document.symmetry)
        start, end = (found.start_x, found.start_y), (found.end_x, found.end_y)
        if len(cells) < document.unit_width * document.unit_height and not backstitch_in_minimal_cell(
            start, end, cells
        ):
            return None
    return found


class BackstitchChain:
    """Backstitch lines that carry on from the last point (owner decision 1).

    The first click sets a start point; each next click stitches a line from
    the last point and becomes the new last point. Clicking the last point
    again stops the chain, as do ``stop()`` (Esc, another tool or target).
    """

    def __init__(self) -> None:
        self.pending: Point | None = None

    def stop(self) -> bool:
        """End the chain. Returns True when one was going."""
        was = self.pending is not None
        self.pending = None
        return was

    def click(self, point: Point, allowed: Callable[[Point, Point], bool]) -> tuple[Point, Point] | None:
        """Handle a click on intersection ``point``; returns the line to stitch, if any.

        A line that ``allowed`` rejects is ignored and the chain stays where it was.
        """
        if self.pending is None:
            self.pending = point
            return None
        if point == self.pending:
            self.pending = None
            return None
        start = self.pending
        if not allowed(start, point):
            return None
        self.pending = point
        return start, point


# Rows and columns -------------------------------------------------------------


@dataclass(frozen=True)
class LineHighlight:
    """Rows/columns to highlight; with ``insertion`` they are gaps where new lines go."""

    columns: tuple[int, ...]
    rows: tuple[int, ...]
    insertion: bool


def line_highlight(document: PatternDocument, axis: Axis, index: int, *, insertion: bool) -> LineHighlight:
    orbit = grid_line_orbit(document, axis, index, insertion=insertion)
    columns = tuple(sorted(value for kind, value in orbit if kind == "column"))
    rows = tuple(sorted(value for kind, value in orbit if kind == "row"))
    return LineHighlight(columns, rows, insertion)


def line_names(highlight: LineHighlight) -> list[tuple[str, int]]:
    """(i18n key, number) of each highlighted line: rows first, 1-based.

    For an insertion these are the numbers of the new lines afterwards.
    """
    def numbers(values: Iterable[int]) -> list[int]:
        values = list(values)
        if highlight.insertion:
            return [gap + k + 1 for k, gap in enumerate(values)]
        return [value + 1 for value in values]

    row_key = "grid.newRowN" if highlight.insertion else "grid.rowN"
    column_key = "grid.newColN" if highlight.insertion else "grid.colN"
    return [(row_key, n) for n in numbers(highlight.rows)] + [
        (column_key, n) for n in numbers(highlight.columns)
    ]


def also_changed(
    document: PatternDocument, axis: Axis, index: int, kind: Literal["before", "after", "remove"]
) -> list[tuple[str, int]]:
    """The other lines the symmetry adds or removes with this action (for "edge.also")."""
    if kind == "remove":
        names = line_names(line_highlight(document, axis, index, insertion=False))
        own = ("grid.colN" if axis == "column" else "grid.rowN", index + 1)
        return [name for name in names if name != own]
    gap = index if kind == "before" else index + 1
    names = line_names(line_highlight(document, axis, gap, insertion=True))
    return names if len(names) > 1 else []


def ruler_label(index: int, size: int, cell_size: int) -> str:
    """Number shown on a ruler button (1-based); sparse when there are many or they are small."""
    sparse = size > 30 or cell_size < 14
    if not sparse or index == 0 or (index + 1) % 5 == 0:
        return str(index + 1)
    return ""


def ruler_cells(box: ViewBox, axis: Axis, cell_size: int) -> list[tuple[int, str, Kind | None]]:
    """(index, label, kind) for each ruler button along ``axis`` of the view."""
    result: list[tuple[int, str, Kind | None]] = []
    if axis == "column":
        size, first, last = box.width, box.x0, box.x1
    else:
        size, first, last = box.height, box.y0, box.y1
    for index in range(first, last + 1):
        # Row/column 0 of the unit is always on the editable part.
        kind = box.kind_at(index, 0) if axis == "column" else box.kind_at(0, index)
        if kind == "extra":
            label = f"+{-index if index < 0 else index - size + 1}"
        elif kind == "unit":
            label = ruler_label(index, size, cell_size)
        else:
            label = ""
        result.append((index, label, kind))
    return result


# Whole band -----------------------------------------------------------------


@dataclass(frozen=True)
class BandLayout:
    """Where each repeat lies in the whole band (as ``renderer.build_colour_grid``)."""

    width: int
    height: int
    x_offsets: tuple[int, ...]
    y_offsets: tuple[int, ...]
    column_counts: tuple[int, ...]
    row_counts: tuple[int, ...]
    top: int
    bottom: int


def band_layout(document: PatternDocument) -> BandLayout:
    columns = [len(_included_column_indices(document, ux)) for ux in range(document.repeats_x)]
    rows = [len(_included_row_indices(document, uy)) for uy in range(document.repeats_y)]
    left, right = document.extension_of("left"), document.extension_of("right")
    top, bottom = document.extension_of("top"), document.extension_of("bottom")
    x_offsets, running = [], left
    for count in columns:
        x_offsets.append(running)
        running += count
    y_offsets, running_y = [], top
    for count in rows:
        y_offsets.append(running_y)
        running_y += count
    return BandLayout(
        left + sum(columns) + right, top + sum(rows) + bottom,
        tuple(x_offsets), tuple(y_offsets), tuple(columns), tuple(rows), top, bottom,
    )


Rect = tuple[int, int, int, int]


def region_rect(layout: BandLayout, target: EditTarget) -> Rect:
    """(x, y, width, height) in band cells of the unit (the middle repeat), an end or a corner."""
    xo, yo = layout.x_offsets, layout.y_offsets
    cols, rows = layout.column_counts, layout.row_counts
    lx, ly = len(xo) - 1, len(yo) - 1
    if target in CORNER_EDGES:
        row_edge, column_edge = CORNER_EDGES[target]
        a = region_rect(layout, cast(Edge, row_edge))
        b = region_rect(layout, cast(Edge, column_edge))
        x0, y0 = max(a[0], b[0]), max(a[1], b[1])
        return x0, y0, min(a[0] + a[2], b[0] + b[2]) - x0, min(a[1] + a[3], b[1] + b[3]) - y0
    if target == "left":
        return 0, 0, xo[0] + cols[0], layout.height
    if target == "right":
        return xo[lx], 0, layout.width - xo[lx], layout.height
    if target == "top":
        return 0, 0, layout.width, yo[0] + rows[0]
    if target == "bottom":
        return 0, yo[ly], layout.width, layout.height - yo[ly]
    mx, my = len(xo) // 2, (len(yo) - 1) // 2
    return xo[mx], yo[my], cols[mx], rows[my]


def region_at(layout: BandLayout, cx: int, cy: int) -> EditTarget | None:
    """What a click on band cell (cx, cy) of the mini band edits.

    Corners take the outer half of a corner repeat (plus its extra rows and
    columns), so the rest of an end stays clickable.
    """
    if not (0 <= cx < layout.width and 0 <= cy < layout.height):
        return None
    xo, yo = layout.x_offsets, layout.y_offsets
    cols, rows = layout.column_counts, layout.row_counts
    lx, ly = len(xo) - 1, len(yo) - 1
    horizontal = "left" if cx < xo[0] + cols[0] / 2 else "right" if cx >= xo[lx] + cols[lx] / 2 else ""
    vertical = "top" if cy < yo[0] + rows[0] / 2 else "bottom" if cy >= yo[ly] + rows[ly] / 2 else ""
    if horizontal and vertical:
        return cast(EditTarget, f"{vertical}_{horizontal}")
    if layout.top and cy < layout.top:
        return "top"
    if layout.bottom and cy >= layout.height - layout.bottom:
        return "bottom"
    if cx < xo[0] + cols[0]:
        return "left"
    if cx >= xo[lx]:
        return "right"
    if len(yo) > 1 and cy < yo[0] + rows[0]:
        return "top"
    if len(yo) > 1 and cy >= yo[ly]:
        return "bottom"
    return "unit"


# SVG paths ------------------------------------------------------------------


def path_grid(columns: int, rows: int, size: float, left: float, top: float) -> str:
    """Grid lines of ``columns`` x ``rows`` cells, on half pixels for crisp 1px lines."""
    right, bottom = left + columns * size, top + rows * size
    parts = [f"M{left + x * size + 0.5:g} {top:g}V{bottom:g}" for x in range(columns + 1)]
    parts += [f"M{left:g} {top + y * size + 0.5:g}H{right:g}" for y in range(rows + 1)]
    return "".join(parts)


def path_rects(rects: Iterable[tuple[float, float, float, float]]) -> str:
    return "".join(f"M{x:g} {y:g}h{w:g}v{h:g}h{-w:g}z" for x, y, w, h in rects)


def path_lines(lines: Iterable[tuple[float, float, float, float]]) -> str:
    return "".join(f"M{x1:g} {y1:g}L{x2:g} {y2:g}" for x1, y1, x2, y2 in lines)


def path_outline(cells: Collection[Cell], size: float, left: float, top: float) -> str:
    """Outline of a set of cells: every cell side with no cell beyond it."""
    parts: list[str] = []
    for x, y in cells:
        px, py = left + x * size, top + y * size
        if (x, y - 1) not in cells:
            parts.append(f"M{px:g} {py:g}h{size:g}")
        if (x, y + 1) not in cells:
            parts.append(f"M{px:g} {py + size:g}h{size:g}")
        if (x - 1, y) not in cells:
            parts.append(f"M{px:g} {py:g}v{size:g}")
        if (x + 1, y) not in cells:
            parts.append(f"M{px + size:g} {py:g}v{size:g}")
    return "".join(parts)
