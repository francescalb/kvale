from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Literal

from kvale.core.model import Backstitch, Mark

SUPPORTED_OPERATIONS = (
    "identity",
    "mirror_x",
    "mirror_y",
    "rotate_180",
    "rotate_90",
    "rotate_270",
    "diag_main",
    "diag_anti",
)

# Operations that only make sense when the recurring unit is square.
SQUARE_ONLY_OPERATIONS = frozenset({"rotate_90", "rotate_270", "diag_main", "diag_anti"})


def normalise_symmetry(
    operations: Iterable[str],
    width: int,
    height: int,
) -> tuple[list[str], list[str]]:
    """Apply the symmetry rules to a selection of operations.

    "identity" is always included, unknown names are dropped, and square-only
    operations are removed when the unit is not square. Returns the allowed
    operations and the square-only operations that were removed, both in the
    order of SUPPORTED_OPERATIONS, so a UI can tell the user what was switched off.
    """
    selected = set(operations) | {"identity"}
    removed: list[str] = []
    if width != height:
        removed = [name for name in SUPPORTED_OPERATIONS if name in selected & SQUARE_ONLY_OPERATIONS]
    allowed = [name for name in SUPPORTED_OPERATIONS if name in selected and name not in removed]
    return allowed, removed


def transform_point(x: int, y: int, width: int, height: int, operation: str) -> tuple[int, int]:
    if operation == "identity":
        return x, y
    if operation == "mirror_x":
        return width - 1 - x, y
    if operation == "mirror_y":
        return x, height - 1 - y
    if operation == "rotate_180":
        return width - 1 - x, height - 1 - y
    if width != height:
        raise ValueError(f"{operation} requires a square recurring unit")
    if operation == "rotate_90":
        return height - 1 - y, x
    if operation == "rotate_270":
        return y, width - 1 - x
    if operation == "diag_main":
        return y, x
    if operation == "diag_anti":
        return width - 1 - y, height - 1 - x
    raise ValueError(f"Unknown symmetry operation: {operation}")


def transform_intersection(
    x: int,
    y: int,
    width: int,
    height: int,
    operation: str,
) -> tuple[int, int]:
    if operation == "identity":
        return x, y
    if operation == "mirror_x":
        return width - x, y
    if operation == "mirror_y":
        return x, height - y
    if operation == "rotate_180":
        return width - x, height - y
    if width != height:
        raise ValueError(f"{operation} requires a square recurring unit")
    if operation == "rotate_90":
        return height - y, x
    if operation == "rotate_270":
        return y, width - x
    if operation == "diag_main":
        return y, x
    if operation == "diag_anti":
        return width - y, height - x
    raise ValueError(f"Unknown symmetry operation: {operation}")


def transform_grid_line(
    axis: Literal["row", "column"],
    index: int,
    operation: str,
    width: int,
    height: int,
    *,
    insertion: bool,
) -> tuple[Literal["row", "column"], int]:
    """Transform a row or column (or, with ``insertion``, a gap between them) by one operation.

    Gaps are numbered 0 to the size, so gap ``i`` lies before row/column ``i``.
    Unknown operations leave the line unchanged.
    """
    x_limit = width if insertion else width - 1
    y_limit = height if insertion else height - 1
    transforms: dict[str, dict[str, tuple[Literal["row", "column"], int]]] = {
        "identity": {"column": ("column", index), "row": ("row", index)},
        "mirror_x": {"column": ("column", x_limit - index), "row": ("row", index)},
        "mirror_y": {"column": ("column", index), "row": ("row", y_limit - index)},
        "rotate_180": {"column": ("column", x_limit - index), "row": ("row", y_limit - index)},
        "rotate_90": {"column": ("row", index), "row": ("column", y_limit - index)},
        "rotate_270": {"column": ("row", x_limit - index), "row": ("column", index)},
        "diag_main": {"column": ("row", index), "row": ("column", index)},
        "diag_anti": {"column": ("row", x_limit - index), "row": ("column", y_limit - index)},
    }
    return transforms.get(operation, transforms["identity"])[axis]


def expand_marks(
    marks: Iterable[Mark],
    width: int,
    height: int,
    operations: Sequence[str],
) -> list[Mark]:
    result: dict[tuple[int, int, int], Mark] = {
        (mark.x, mark.y, mark.colour_slot): mark
        for mark in marks
    }

    changed = True

    while changed:
        changed = False

        # Make a copy because new marks may be added during this pass.
        current_marks = list(result.values())

        for mark in current_marks:
            for operation in operations:
                tx, ty = transform_point(
                    mark.x,
                    mark.y,
                    width,
                    height,
                    operation,
                )

                if not (0 <= tx < width and 0 <= ty < height):
                    continue

                key = (tx, ty, mark.colour_slot)

                if key not in result:
                    result[key] = Mark(
                        x=tx,
                        y=ty,
                        colour_slot=mark.colour_slot,
                    )
                    changed = True

    return list(result.values())


def expand_backstitches(
    backstitches: Iterable[Backstitch],
    width: int,
    height: int,
    operations: Sequence[str],
) -> list[Backstitch]:
    result = {backstitch.key: backstitch for backstitch in backstitches}
    changed = True
    while changed:
        changed = False
        for backstitch in list(result.values()):
            for operation in operations:
                start_x, start_y = transform_intersection(
                    backstitch.start_x,
                    backstitch.start_y,
                    width,
                    height,
                    operation,
                )
                end_x, end_y = transform_intersection(
                    backstitch.end_x,
                    backstitch.end_y,
                    width,
                    height,
                    operation,
                )
                transformed = Backstitch(
                    start_x,
                    start_y,
                    end_x,
                    end_y,
                    backstitch.colour_slot,
                )
                if transformed.key not in result:
                    result[transformed.key] = transformed
                    changed = True
    return list(result.values())
