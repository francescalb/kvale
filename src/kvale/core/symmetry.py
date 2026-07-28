from __future__ import annotations

from collections.abc import Iterable, Sequence

from kvale.core.model import Mark


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