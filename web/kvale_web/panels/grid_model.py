"""The "Repeat and size" card and the Symmetry card without the DOM.

Number fields, the edge toggles and their diagram, and the symmetry tiles
with their small pictures. Runs in plain CPython.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from kvale.core.model import PatternDocument
from kvale.core.renderer import _included_column_indices, _included_row_indices
from kvale.core.symmetry import SQUARE_ONLY_OPERATIONS, SUPPORTED_OPERATIONS, transform_point

GRID_MIN = 1
GRID_MAX = 100
# The number fields of the card: document attribute -> i18n key of its label.
GRID_FIELDS: dict[str, str] = {
    "unit_width": "grid.width",
    "unit_height": "grid.height",
    "repeats_x": "grid.across",
    "repeats_y": "grid.down",
}
# The edge toggles, in the design's order: edge -> document attribute.
EDGE_FIELDS: dict[str, str] = {
    "left": "repeat_left_column",
    "right": "repeat_right_column",
    "top": "repeat_top_row",
    "bottom": "repeat_bottom_row",
}

# Symmetry tiles: the first group works on any repeat, the second needs a square.
SYMMETRY_GROUPS: tuple[tuple[str, ...], tuple[str, ...]] = (
    tuple(op for op in SUPPORTED_OPERATIONS if op not in SQUARE_ONLY_OPERATIONS),
    tuple(op for op in SUPPORTED_OPERATIONS if op in SQUARE_ONLY_OPERATIONS),
)


def clamp_setting(value: object) -> int | None:
    """A number field's value as a whole number from 1 to 100; None when not a number."""
    try:
        number = float(str(value).strip().replace(",", "."))
    except ValueError:
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return max(GRID_MIN, min(GRID_MAX, round(number)))


def toggled_symmetry(current: list[str], operation: str) -> list[str]:
    """The selection after tapping ``operation`` ("identity" cannot be switched off)."""
    if operation == "identity":
        return list(current)
    if operation in current:
        return [op for op in current if op != operation]
    return [op for op in SUPPORTED_OPERATIONS if op == operation or op in current]


def square_size(document: PatternDocument) -> int:
    """The side of the square the "Make the repeat n × n" button offers."""
    return max(document.unit_width, document.unit_height)


# Seed cells of the symmetry pictures, on a 6 x 6 grid of 7-unit cells.
_ICON_SEED = ((1, 0), (2, 0), (2, 1))
_ICON_CELLS = 6
_ICON_CELL = 7


def symmetry_icon(operation: str) -> str:
    """Inline SVG showing what ``operation`` does to three seed stitches."""
    n, c = _ICON_CELLS, _ICON_CELL
    size = n * c
    cells: dict[tuple[int, int], bool] = {cell: True for cell in _ICON_SEED}
    if operation != "identity":
        for x, y in _ICON_SEED:
            cells.setdefault(transform_point(x, y, n, n, operation), False)
    parts = [
        f'<svg viewBox="-1 -1 {size + 2} {size + 2}" aria-hidden="true">',
        f'<rect x="0" y="0" width="{size}" height="{size}" fill="none" stroke="currentColor" stroke-opacity=".35"/>',
    ]
    for (x, y), seed in cells.items():
        parts.append(
            f'<rect x="{x * c + 0.8:g}" y="{y * c + 0.8:g}" width="{c - 1.6:g}" height="{c - 1.6:g}" '
            f'rx="1" fill="currentColor" fill-opacity="{1 if seed else 0.45}"/>'
        )
    half = size / 2
    axis = {
        "mirror_x": f"M{half:g} -1V{size + 1}",
        "mirror_y": f"M-1 {half:g}H{size + 1}",
        "diag_main": f"M0 0L{size} {size}",
        "diag_anti": f"M{size} 0L0 {size}",
    }.get(operation)
    if axis:
        parts.append(f'<path d="{axis}" stroke="currentColor" stroke-dasharray="3 2" stroke-width="1.2"/>')
    if operation.startswith("rotate"):
        parts.append(f'<circle cx="{half:g}" cy="{half:g}" r="2" fill="currentColor"/>')
    parts.append("</svg>")
    return "".join(parts)


@dataclass(frozen=True)
class DiagramCell:
    x: int
    y: int
    # "column" (an outer column), "row" (an outer row) or "inner".
    kind: str


@dataclass(frozen=True)
class EdgeDiagram:
    width: int
    height: int
    cells: tuple[DiagramCell, ...]
    # Outline of each repeat: (x, y, width, height) in cells.
    units: tuple[tuple[int, int, int, int], ...]


def edge_diagram(document: PatternDocument) -> EdgeDiagram:
    """A 3 x 2 band of 5 x 4 repeats with the document's edge toggles, as the renderer joins them."""
    sample = PatternDocument(
        unit_width=5,
        unit_height=4,
        repeats_x=3,
        repeats_y=2,
        **{name: getattr(document, name) for name in EDGE_FIELDS.values()},
    )
    columns = [_included_column_indices(sample, unit) for unit in range(sample.repeats_x)]
    rows = [_included_row_indices(sample, unit) for unit in range(sample.repeats_y)]
    cells: list[DiagramCell] = []
    units: list[tuple[int, int, int, int]] = []
    top = 0
    for unit_rows in rows:
        left = 0
        for unit_columns in columns:
            for iy, local_y in enumerate(unit_rows):
                for ix, local_x in enumerate(unit_columns):
                    if local_x in (0, sample.unit_width - 1):
                        kind = "column"
                    elif local_y in (0, sample.unit_height - 1):
                        kind = "row"
                    else:
                        kind = "inner"
                    cells.append(DiagramCell(left + ix, top + iy, kind))
            units.append((left, top, len(unit_columns), len(unit_rows)))
            left += len(unit_columns)
        top += len(unit_rows)
    width = sum(len(c) for c in columns)
    height = sum(len(r) for r in rows)
    return EdgeDiagram(width, height, tuple(cells), tuple(units))
