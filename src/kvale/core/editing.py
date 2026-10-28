"""Edit operations on a PatternDocument.

Every function changes the document in place and keeps it consistent: marks
and backstitches stay inside the area they belong to and the symmetry rules
from ``normalise_symmetry`` hold after any change to the unit size. Functions
that can switch off symmetry operations return the names of those operations
so a UI can tell the user; the others return True when they changed the
document. Use ``kvale.core.editor.Editor`` to get undo/redo.

Coordinates: cells are numbered from (0, 0) in the top-left corner of the
recurring unit. Backstitches run between grid intersections, numbered the
same way, so the unit's intersections go from (0, 0) to (unit_width,
unit_height). An end piece (``RepeatOverride``) uses the unit's coordinates
and may reach ``extension`` cells beyond the unit on its own side: negative
coordinates for the top and left end pieces, coordinates from unit_width or
unit_height upwards for the right and bottom ones.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from math import hypot
from typing import Literal, cast

from kvale.core.model import (
    Backstitch,
    BackstitchKey,
    Cell,
    Mark,
    PatternDocument,
    RepeatOverride,
)
from kvale.core.symmetry import (
    expand_backstitches,
    expand_marks,
    normalise_symmetry,
    transform_grid_line,
)

# Longest colour sequence a UI should offer for one slot.
MAX_SEQUENCE_LENGTH = 24

Edge = Literal["top", "bottom", "left", "right"]
# What a UI is editing: the recurring unit or one of the end pieces.
Target = Literal["unit", "top", "bottom", "left", "right"]
Axis = Literal["row", "column"]

EDGES: tuple[Edge, ...] = ("top", "bottom", "left", "right")

# How far from a backstitch (in cells) a click may be and still hit it.
BACKSTITCH_HIT_DISTANCE = 0.35


# Unit marks ---------------------------------------------------------------


def find_source_mark(document: PatternDocument, x: int, y: int) -> Mark | None:
    """Find the stored mark responsible for a displayed cell in the unit.

    The cell may hold the stored mark itself or one of its symmetry-generated
    copies. When several marks reach the cell, the first in the motif wins.
    """
    for mark in document.motif:
        generated_marks = expand_marks(
            [mark],
            width=document.unit_width,
            height=document.unit_height,
            operations=document.symmetry,
        )
        for generated in generated_marks:
            if generated.x == x and generated.y == y:
                return mark
    return None


def _in_unit(document: PatternDocument, x: int, y: int) -> bool:
    return 0 <= x < document.unit_width and 0 <= y < document.unit_height


def paint_cell(document: PatternDocument, x: int, y: int, colour_slot: int) -> bool:
    """Paint a displayed cell of the unit with a colour slot.

    Painting a generated copy recolours the stored mark that generated it;
    painting an empty cell adds a new mark there. Returns False when the cell
    is outside the unit or already has that colour.
    """
    if not _in_unit(document, x, y):
        return False
    source_mark = find_source_mark(document, x, y)
    if source_mark is not None:
        if source_mark.colour_slot == colour_slot:
            return False
        x, y = source_mark.x, source_mark.y
    document.set_mark(x, y, colour_slot)
    return True


def erase_cell(document: PatternDocument, x: int, y: int) -> bool:
    """Erase the stored mark that produces a displayed cell of the unit.

    Erasing a generated copy removes the stored mark and with it all its
    copies. Returns False when there was nothing to erase.
    """
    if not _in_unit(document, x, y):
        return False
    source_mark = find_source_mark(document, x, y)
    if source_mark is None:
        return False
    document.erase_mark(source_mark.x, source_mark.y)
    return True


# Unit backstitches --------------------------------------------------------


def find_source_backstitch(document: PatternDocument, key: BackstitchKey) -> Backstitch | None:
    """Find the stored backstitch that produces a displayed backstitch in the unit."""
    for backstitch in document.backstitches:
        generated = expand_backstitches(
            [backstitch],
            document.unit_width,
            document.unit_height,
            document.symmetry,
        )
        if any(item.key == key for item in generated):
            return backstitch
    return None


def add_backstitch(
    document: PatternDocument,
    start: tuple[int, int],
    end: tuple[int, int],
    colour_slot: int,
) -> bool:
    """Add a backstitch between two intersections of the unit.

    Drawing over a generated copy recolours the stored backstitch that
    generated it. Returns False when the end points are the same, outside the
    unit, or the backstitch already has that colour.
    """
    if start == end or not all(_intersection_in(document, "unit", point) for point in (start, end)):
        return False
    candidate = Backstitch(start[0], start[1], end[0], end[1], colour_slot)
    source = find_source_backstitch(document, candidate.key)
    if source is not None:
        if source.colour_slot == colour_slot:
            return False
        candidate = Backstitch(source.start_x, source.start_y, source.end_x, source.end_y, colour_slot)
    document.set_backstitch(candidate)
    return True


def _distance_to_segment(point_x: float, point_y: float, backstitch: Backstitch) -> float:
    start_x, start_y = backstitch.start_x, backstitch.start_y
    delta_x = backstitch.end_x - start_x
    delta_y = backstitch.end_y - start_y
    length_squared = delta_x * delta_x + delta_y * delta_y
    if length_squared == 0:
        return hypot(point_x - start_x, point_y - start_y)
    amount = ((point_x - start_x) * delta_x + (point_y - start_y) * delta_y) / length_squared
    amount = max(0.0, min(1.0, amount))
    nearest_x = start_x + amount * delta_x
    nearest_y = start_y + amount * delta_y
    return hypot(point_x - nearest_x, point_y - nearest_y)


def visible_backstitches(document: PatternDocument, target: Target = "unit") -> list[Backstitch]:
    """The backstitches shown when editing ``target``, in drawing order.

    For the unit these are the stored backstitches and their symmetry copies.
    For an end piece, the end piece's hidden backstitches are left out and its
    added ones are included.
    """
    expanded = expand_backstitches(
        document.backstitches,
        document.unit_width,
        document.unit_height,
        document.symmetry,
    )
    if target == "unit":
        return expanded
    stitches = {item.key: item for item in expanded}
    override = get_end_piece(document, target)
    if override is not None:
        for key in override.removed_backstitches:
            stitches.pop(key, None)
        for item in override.added_backstitches:
            stitches[item.key] = item
    return list(stitches.values())


def hidden_backstitches(document: PatternDocument, edge: Edge) -> list[Backstitch]:
    """The unit backstitches that the end piece on ``edge`` hides."""
    override = get_end_piece(document, edge)
    if override is None:
        return []
    base = {
        item.key: item
        for item in expand_backstitches(
            document.backstitches,
            document.unit_width,
            document.unit_height,
            document.symmetry,
        )
    }
    return [base[key] for key in override.removed_backstitches if key in base]


def find_backstitch_near(
    document: PatternDocument,
    x: float,
    y: float,
    target: Target = "unit",
    max_distance: float = BACKSTITCH_HIT_DISTANCE,
) -> Backstitch | None:
    """The visible backstitch closest to point (x, y), if within ``max_distance`` cells."""
    candidates = visible_backstitches(document, target)
    if not candidates:
        return None
    nearest = min(candidates, key=lambda item: _distance_to_segment(x, y, item))
    if _distance_to_segment(x, y, nearest) > max_distance:
        return None
    return nearest


def erase_backstitch_near(
    document: PatternDocument,
    x: float,
    y: float,
    target: Target = "unit",
) -> bool:
    """Erase the visible backstitch nearest to point (x, y) when editing ``target``.

    In the unit this removes the stored backstitch behind it (and so all its
    copies). In an end piece a unit backstitch is hidden and an added one is
    removed. Returns False when no backstitch is close enough.
    """
    nearest = find_backstitch_near(document, x, y, target)
    if nearest is None:
        return False
    if target == "unit":
        source = find_source_backstitch(document, nearest.key)
        if source is None:
            return False
        document.erase_backstitch(source.key)
        return True
    base_keys = {
        item.key
        for item in expand_backstitches(
            document.backstitches,
            document.unit_width,
            document.unit_height,
            document.symmetry,
        )
    }
    override = ensure_end_piece(document, target)
    if nearest.key in base_keys:
        override.hide_backstitch(nearest.key)
    else:
        override.added_backstitches = [
            item for item in override.added_backstitches if item.key != nearest.key
        ]
    return True


# End pieces ---------------------------------------------------------------


def get_end_piece(document: PatternDocument, edge: Edge) -> RepeatOverride | None:
    """The end piece (repeat override) on ``edge``, or None if it has none."""
    return cast(RepeatOverride | None, getattr(document, f"{edge}_repeat_override"))


def ensure_end_piece(document: PatternDocument, edge: Edge) -> RepeatOverride:
    """The end piece on ``edge``, created empty if needed."""
    override = get_end_piece(document, edge)
    if override is None:
        override = RepeatOverride()
        setattr(document, f"{edge}_repeat_override", override)
    return override


def editor_bounds(document: PatternDocument, target: Target) -> tuple[int, int, int, int]:
    """Cell range ``(min_x, max_x, min_y, max_y)`` (inclusive) shown when editing ``target``.

    An end piece covers the unit plus its extension on its own side.
    """
    if target == "unit":
        return 0, document.unit_width - 1, 0, document.unit_height - 1
    override = get_end_piece(document, target)
    extension = override.extension if override else 0
    return _end_piece_bounds(document.unit_width, document.unit_height, target, extension)


def _end_piece_bounds(
    width: int, height: int, edge: Edge, extension: int
) -> tuple[int, int, int, int]:
    minimum_x = -extension if edge == "left" else 0
    maximum_x = width + extension - 1 if edge == "right" else width - 1
    minimum_y = -extension if edge == "top" else 0
    maximum_y = height + extension - 1 if edge == "bottom" else height - 1
    return minimum_x, maximum_x, minimum_y, maximum_y


def _intersection_in(document: PatternDocument, target: Target, point: tuple[int, int]) -> bool:
    minimum_x, maximum_x, minimum_y, maximum_y = editor_bounds(document, target)
    return minimum_x <= point[0] <= maximum_x + 1 and minimum_y <= point[1] <= maximum_y + 1


def intersection_in_editor(document: PatternDocument, target: Target, x: int, y: int) -> bool:
    """True when intersection (x, y) can be a backstitch end point when editing ``target``."""
    return _intersection_in(document, target, (x, y))


def paint_end_piece_cell(
    document: PatternDocument, edge: Edge, x: int, y: int, colour_slot: int
) -> bool:
    """Paint a cell of the end piece on ``edge``.

    Painting a unit cell in its own colour clears any change the end piece
    made there; any other colour is stored as an added mark. Returns False
    when the cell is outside the end piece or already shows that colour.
    """
    minimum_x, maximum_x, minimum_y, maximum_y = editor_bounds(document, edge)
    if not (minimum_x <= x <= maximum_x and minimum_y <= y <= maximum_y):
        return False
    expanded = expand_marks(document.motif, document.unit_width, document.unit_height, document.symmetry)
    base_colour = next((mark.colour_slot for mark in expanded if mark.x == x and mark.y == y), None)
    override = get_end_piece(document, edge)
    existing = (
        next((mark for mark in override.added_marks if mark.x == x and mark.y == y), None)
        if override
        else None
    )
    removed = Cell(x, y) in override.removed_cells if override else False
    if existing is not None and existing.colour_slot == colour_slot:
        return False
    if existing is None and not removed and base_colour == colour_slot:
        return False

    override = ensure_end_piece(document, edge)
    if base_colour == colour_slot:
        override.removed_cells = [
            cell for cell in override.removed_cells if not (cell.x == x and cell.y == y)
        ]
        override.remove_added_mark(x, y)
    else:
        override.set_mark(x, y, colour_slot)
    return True


def erase_end_piece_cell(document: PatternDocument, edge: Edge, x: int, y: int) -> bool:
    """Erase a cell of the end piece on ``edge``.

    A unit cell is hidden in the end piece; an added mark is removed. Returns
    False when the cell is outside the end piece or already empty.
    """
    minimum_x, maximum_x, minimum_y, maximum_y = editor_bounds(document, edge)
    if not (minimum_x <= x <= maximum_x and minimum_y <= y <= maximum_y):
        return False
    expanded = expand_marks(document.motif, document.unit_width, document.unit_height, document.symmetry)
    has_base = any(mark.x == x and mark.y == y for mark in expanded)
    override = get_end_piece(document, edge)
    has_added = bool(override and any(mark.x == x and mark.y == y for mark in override.added_marks))
    is_removed = bool(override and Cell(x, y) in override.removed_cells)
    if (not has_base and not has_added) or (has_base and is_removed and not has_added):
        return False

    override = ensure_end_piece(document, edge)
    if _in_unit(document, x, y) and has_base:
        override.hide_cell(x, y)
    else:
        override.remove_added_mark(x, y)
    return True


def add_end_piece_backstitch(
    document: PatternDocument,
    edge: Edge,
    start: tuple[int, int],
    end: tuple[int, int],
    colour_slot: int,
) -> bool:
    """Add a backstitch to the end piece on ``edge``.

    Drawing over a unit backstitch in its own colour clears any change the
    end piece made to it. Returns False when nothing changes.
    """
    if start == end or not all(_intersection_in(document, edge, point) for point in (start, end)):
        return False
    candidate = Backstitch(start[0], start[1], end[0], end[1], colour_slot)
    expanded = {
        item.key: item
        for item in expand_backstitches(
            document.backstitches,
            document.unit_width,
            document.unit_height,
            document.symmetry,
        )
    }
    override = get_end_piece(document, edge)
    base = expanded.get(candidate.key)
    existing = (
        next((item for item in override.added_backstitches if item.key == candidate.key), None)
        if override
        else None
    )
    removed = candidate.key in override.removed_backstitches if override else False
    if existing is not None and existing.colour_slot == candidate.colour_slot:
        return False
    if (
        existing is None
        and not removed
        and base is not None
        and base.colour_slot == candidate.colour_slot
    ):
        return False

    override = ensure_end_piece(document, edge)
    if base is not None and base.colour_slot == candidate.colour_slot:
        override.restore_backstitch(candidate.key)
    else:
        override.set_backstitch(candidate)
    return True


def set_end_piece_extension(document: PatternDocument, edge: Edge, extension: int) -> bool:
    """Set how many rows/columns the end piece on ``edge`` adds beyond the unit.

    Negative values are raised to 0. Added marks and backstitches that fall
    outside the new extension are removed. Returns False when nothing changes.
    """
    extension = max(0, extension)
    override = get_end_piece(document, edge)
    if (override.extension if override else 0) == extension:
        return False
    override = ensure_end_piece(document, edge)
    override.extension = extension
    width, height = document.unit_width, document.unit_height
    if edge == "top":
        override.added_marks = [mark for mark in override.added_marks if mark.y >= -extension]
    elif edge == "bottom":
        override.added_marks = [mark for mark in override.added_marks if mark.y < height + extension]
    elif edge == "left":
        override.added_marks = [mark for mark in override.added_marks if mark.x >= -extension]
    else:
        override.added_marks = [mark for mark in override.added_marks if mark.x < width + extension]
    minimum_x, maximum_x, minimum_y, maximum_y = _end_piece_bounds(width, height, edge, extension)
    override.added_backstitches = [
        backstitch
        for backstitch in override.added_backstitches
        if all(
            minimum_x <= x <= maximum_x + 1 and minimum_y <= y <= maximum_y + 1
            for x, y in (
                (backstitch.start_x, backstitch.start_y),
                (backstitch.end_x, backstitch.end_y),
            )
        )
    ]
    return True


def reset_end_piece(document: PatternDocument, edge: Edge) -> bool:
    """Remove the end piece on ``edge``. Returns False when there was none."""
    if get_end_piece(document, edge) is None:
        return False
    setattr(document, f"{edge}_repeat_override", None)
    return True


# Grid ---------------------------------------------------------------------


def set_symmetry(document: PatternDocument, operations: Iterable[str]) -> list[str]:
    """Set the symmetry operations, applying the rules in ``normalise_symmetry``.

    Returns the square-only operations that were removed.
    """
    document.symmetry, removed = normalise_symmetry(
        operations, document.unit_width, document.unit_height
    )
    return removed


def _enforce_symmetry_rules(document: PatternDocument) -> list[str]:
    return set_symmetry(document, document.symmetry)


def grid_line_orbit(
    document: PatternDocument, axis: Axis, index: int, *, insertion: bool
) -> set[tuple[Axis, int]]:
    """Every row/column that the symmetry ties to row/column ``index``.

    With ``insertion`` the index is a gap between lines (0 to the size)
    instead of a line, as used when inserting.
    """
    width = document.unit_width
    height = document.unit_height
    result: set[tuple[Axis, int]] = {(axis, index)}
    pending: list[tuple[Axis, int]] = [(axis, index)]
    operations = document.symmetry or ["identity"]
    while pending:
        current_axis, current_index = pending.pop()
        for operation in operations:
            transformed = transform_grid_line(
                current_axis, current_index, operation, width, height, insertion=insertion
            )
            if transformed not in result:
                result.add(transformed)
                pending.append(transformed)
    return result


def _orbit_lines(
    document: PatternDocument, axis: Axis, index: int, *, insertion: bool
) -> tuple[list[int], list[int]]:
    upper_bound = (document.unit_width if axis == "column" else document.unit_height) - (
        0 if insertion else 1
    )
    index = max(0, min(index, upper_bound))
    orbit = grid_line_orbit(document, axis, index, insertion=insertion)
    columns = sorted(value for kind, value in orbit if kind == "column")
    rows = sorted(value for kind, value in orbit if kind == "row")
    return columns, rows


def can_remove_grid_line(document: PatternDocument, axis: Axis, index: int) -> bool:
    """False when removing the line (and its symmetric partners) would empty the unit."""
    columns, rows = _orbit_lines(document, axis, index, insertion=False)
    return document.unit_width - len(columns) >= 1 and document.unit_height - len(rows) >= 1


def change_grid_line(
    document: PatternDocument, axis: Axis, index: int, *, insertion: bool
) -> list[str]:
    """Insert an empty row/column before ``index``, or remove the one at ``index``.

    The index is clamped to the unit. The symmetry may tie other rows and
    columns to this one; they are inserted or removed as well, so the motif
    stays symmetric. Marks, backstitches and end pieces move with the grid;
    whatever lay on a removed line is dropped. A removal that would leave no
    row or column does nothing (see ``can_remove_grid_line``).
    """
    width = document.unit_width
    height = document.unit_height
    columns, rows = _orbit_lines(document, axis, index, insertion=insertion)
    if not insertion and (width - len(columns) < 1 or height - len(rows) < 1):
        return []

    _move_for_grid_change(document, columns, rows, insertion=insertion)
    if insertion:
        document.motif = [
            Mark(
                mark.x + sum(position <= mark.x for position in columns),
                mark.y + sum(position <= mark.y for position in rows),
                mark.colour_slot,
            )
            for mark in document.motif
        ]
        document.unit_width = width + len(columns)
        document.unit_height = height + len(rows)
    else:
        removed_columns = set(columns)
        removed_rows = set(rows)
        document.motif = [
            Mark(
                mark.x - sum(position < mark.x for position in columns),
                mark.y - sum(position < mark.y for position in rows),
                mark.colour_slot,
            )
            for mark in document.motif
            if mark.x not in removed_columns and mark.y not in removed_rows
        ]
        document.unit_width = width - len(columns)
        document.unit_height = height - len(rows)
    return _enforce_symmetry_rules(document)


def _move_for_grid_change(
    document: PatternDocument, columns: list[int], rows: list[int], *, insertion: bool
) -> None:
    removed_columns = set(columns)
    removed_rows = set(rows)

    def move_point(x: int, y: int) -> tuple[int, int]:
        if insertion:
            return (
                x + sum(position <= x for position in columns),
                y + sum(position <= y for position in rows),
            )
        return (
            x - sum(position < x for position in columns),
            y - sum(position < y for position in rows),
        )

    def move_cell(x: int, y: int) -> tuple[int, int] | None:
        if not insertion and (x in removed_columns or y in removed_rows):
            return None
        return move_point(x, y)

    def move_backstitch(backstitch: Backstitch) -> Backstitch | None:
        start = move_point(backstitch.start_x, backstitch.start_y)
        end = move_point(backstitch.end_x, backstitch.end_y)
        if start == end:
            return None
        return Backstitch(*start, *end, backstitch.colour_slot)

    def move_key(key: BackstitchKey) -> BackstitchKey | None:
        start = move_point(key.start_x, key.start_y)
        end = move_point(key.end_x, key.end_y)
        if start == end:
            return None
        return BackstitchKey.between(*start, *end)

    document.backstitches = [
        moved for backstitch in document.backstitches if (moved := move_backstitch(backstitch))
    ]
    for edge in EDGES:
        override = get_end_piece(document, edge)
        if override is None:
            continue
        override.removed_cells = [
            Cell(*moved_cell)
            for cell in override.removed_cells
            if (moved_cell := move_cell(cell.x, cell.y))
        ]
        override.added_marks = [
            Mark(*moved_mark, mark.colour_slot)
            for mark in override.added_marks
            if (moved_mark := move_cell(mark.x, mark.y))
        ]
        override.removed_backstitches = [
            moved_key for key in override.removed_backstitches if (moved_key := move_key(key))
        ]
        override.added_backstitches = [
            moved_stitch
            for backstitch in override.added_backstitches
            if (moved_stitch := move_backstitch(backstitch))
        ]


def insert_column(document: PatternDocument, index: int) -> list[str]:
    """Insert an empty column before ``index``; see ``change_grid_line``."""
    return change_grid_line(document, "column", index, insertion=True)


def remove_column(document: PatternDocument, index: int) -> list[str]:
    """Remove the column at ``index``; see ``change_grid_line``."""
    return change_grid_line(document, "column", index, insertion=False)


def insert_row(document: PatternDocument, index: int) -> list[str]:
    """Insert an empty row before ``index``; see ``change_grid_line``."""
    return change_grid_line(document, "row", index, insertion=True)


def remove_row(document: PatternDocument, index: int) -> list[str]:
    """Remove the row at ``index``; see ``change_grid_line``."""
    return change_grid_line(document, "row", index, insertion=False)


GridPlace = Literal["top_row", "bottom_row", "first_column", "last_column", "row", "column"]


def grid_line_for_place(
    document: PatternDocument, place: GridPlace, *, insertion: bool, number: int = 1
) -> tuple[Axis, int]:
    """Translate a place chosen in a UI to ``(axis, index)`` for ``change_grid_line``.

    ``number`` is the 1-based row or column number for the places "row" and
    "column". Inserting at the bottom row or last column adds after it.
    """
    if place == "top_row":
        return "row", 0
    if place == "bottom_row":
        return "row", document.unit_height if insertion else document.unit_height - 1
    if place == "first_column":
        return "column", 0
    if place == "last_column":
        return "column", document.unit_width if insertion else document.unit_width - 1
    return place, number - 1


def max_line_number(document: PatternDocument, axis: Axis, *, insertion: bool) -> int:
    """Highest 1-based row/column number a UI should offer for ``change_grid_line``."""
    limit = document.unit_height if axis == "row" else document.unit_width
    return limit + 1 if insertion else limit


def resize_unit(document: PatternDocument, width: int, height: int) -> list[str]:
    """Resize the unit from its top-left corner, dropping what falls outside.

    Sizes below 1 are raised to 1. Added marks and backstitches in the
    extension of the bottom and right end pieces move with the unit's edge.
    """
    old_width, old_height = document.unit_width, document.unit_height
    new_width, new_height = max(1, width), max(1, height)
    _resize_end_pieces(document, old_width, old_height, new_width, new_height)
    document.unit_width = new_width
    document.unit_height = new_height
    document.motif = [
        mark
        for mark in document.motif
        if mark.x < document.unit_width and mark.y < document.unit_height
    ]
    return _enforce_symmetry_rules(document)


def _resize_end_pieces(
    document: PatternDocument, old_width: int, old_height: int, new_width: int, new_height: int
) -> None:
    def inside(points: Iterable[tuple[int, int]], bounds: tuple[int, int, int, int]) -> bool:
        minimum_x, maximum_x, minimum_y, maximum_y = bounds
        return all(minimum_x <= x <= maximum_x and minimum_y <= y <= maximum_y for x, y in points)

    def endpoints(backstitch: Backstitch | BackstitchKey) -> list[tuple[int, int]]:
        return [(backstitch.start_x, backstitch.start_y), (backstitch.end_x, backstitch.end_y)]

    unit_intersections = (0, new_width, 0, new_height)
    document.backstitches = [
        backstitch
        for backstitch in document.backstitches
        if inside(endpoints(backstitch), unit_intersections)
    ]
    for edge in EDGES:
        override = get_end_piece(document, edge)
        if override is None:
            continue
        override.removed_cells = [
            cell for cell in override.removed_cells if cell.x < new_width and cell.y < new_height
        ]
        override.removed_backstitches = [
            key for key in override.removed_backstitches if inside(endpoints(key), unit_intersections)
        ]

        def move(x: int, y: int, edge: Edge = edge) -> tuple[int, int]:
            if edge == "right" and x >= old_width:
                x += new_width - old_width
            if edge == "bottom" and y >= old_height:
                y += new_height - old_height
            return x, y

        cell_bounds = _end_piece_bounds(new_width, new_height, edge, override.extension)
        minimum_x, maximum_x, minimum_y, maximum_y = cell_bounds
        intersection_bounds = (minimum_x, maximum_x + 1, minimum_y, maximum_y + 1)
        adjusted: list[Mark] = []
        for mark in override.added_marks:
            x, y = move(mark.x, mark.y)
            if inside([(x, y)], cell_bounds):
                adjusted.append(Mark(x, y, mark.colour_slot))
        override.added_marks = adjusted
        adjusted_backstitches: list[Backstitch] = []
        for backstitch in override.added_backstitches:
            points = [move(x, y) for x, y in endpoints(backstitch)]
            if inside(points, intersection_bounds) and points[0] != points[1]:
                adjusted_backstitches.append(Backstitch(*points[0], *points[1], backstitch.colour_slot))
        override.added_backstitches = adjusted_backstitches


def set_repeats(document: PatternDocument, repeats_x: int, repeats_y: int) -> None:
    """Set the number of repeats across and down. Counts below 1 are raised to 1."""
    document.repeats_x = max(1, repeats_x)
    document.repeats_y = max(1, repeats_y)


# Colours ------------------------------------------------------------------


def add_palette_colour(document: PatternDocument, colour: str) -> int:
    """Add a colour slot with a one-colour sequence and return its index."""
    document.palette_sequences.append([colour])
    return len(document.palette_sequences) - 1


def set_palette_sequence(document: PatternDocument, index: int, sequence: Sequence[str]) -> None:
    """Replace the colour sequence of slot ``index``. The first colour is the base colour."""
    if not 0 <= index < len(document.palette_sequences):
        raise IndexError(f"No colour slot {index}")
    if not sequence:
        raise ValueError("A palette sequence must contain at least one colour")
    document.palette_sequences[index] = list(sequence)


def resize_sequence(sequence: Sequence[str], length: int) -> list[str]:
    """Return ``sequence`` cut or extended to ``length`` (at least 1) colours.

    New entries repeat the last colour.
    """
    if not sequence:
        raise ValueError("A palette sequence must contain at least one colour")
    length = max(1, length)
    result = list(sequence[:length])
    result.extend([sequence[-1]] * (length - len(result)))
    return result
