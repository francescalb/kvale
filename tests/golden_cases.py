"""Input documents for the golden tests in test_golden.py.

The expected output in tests/data/golden/ was generated from the
add_rm_col_rows branch (commit 0e46630) before it was merged into main, with
tests/generate_golden.py. Do not regenerate it to make a failing test pass:
a difference means the behaviour of the program changed.
"""

from __future__ import annotations

from typing import Any

_BASE_PALETTE = [["#b1172b"], ["#2d7d32"], ["#f2c84b"], ["#1b1b1b"]]


def _marks(*items: tuple[int, int, int]) -> list[dict[str, int]]:
    return [{"x": x, "y": y, "colour_slot": slot} for x, y, slot in items]


def _stitches(*items: tuple[int, int, int, int, int]) -> list[dict[str, int]]:
    return [
        {"start_x": sx, "start_y": sy, "end_x": ex, "end_y": ey, "colour_slot": slot}
        for sx, sy, ex, ey, slot in items
    ]


def _keys(*items: tuple[int, int, int, int]) -> list[dict[str, int]]:
    return [{"start_x": sx, "start_y": sy, "end_x": ex, "end_y": ey} for sx, sy, ex, ey in items]


def _cells(*items: tuple[int, int]) -> list[dict[str, int]]:
    return [{"x": x, "y": y} for x, y in items]


CASES: dict[str, dict[str, Any]] = {
    # Square unit with every symmetry operation and backstitches.
    "symmetry-all": {
        "unit_width": 8,
        "unit_height": 8,
        "repeats_x": 3,
        "repeats_y": 2,
        "background": "#ffffff",
        "palette_sequences": _BASE_PALETTE,
        "symmetry": [
            "identity",
            "mirror_x",
            "mirror_y",
            "rotate_180",
            "rotate_90",
            "rotate_270",
            "diag_main",
            "diag_anti",
        ],
        "motif": _marks((1, 0, 0), (2, 1, 1), (3, 3, 2), (0, 2, 3)),
        "backstitches": _stitches((1, 1, 2, 2, 3), (0, 4, 1, 4, 0)),
    },
    # Non-square unit with mirrors only, and some outer rows/columns not repeated.
    "edges-mirror": {
        "unit_width": 7,
        "unit_height": 5,
        "repeats_x": 4,
        "repeats_y": 3,
        "repeat_left_column": False,
        "repeat_right_column": True,
        "repeat_top_row": True,
        "repeat_bottom_row": False,
        "background": "#f5f1e8",
        "palette_sequences": _BASE_PALETTE,
        "symmetry": ["identity", "mirror_x", "mirror_y"],
        "motif": _marks((0, 0, 0), (1, 2, 1), (3, 4, 2), (6, 1, 3)),
        "backstitches": _stitches((0, 0, 1, 1, 1), (3, 0, 3, 5, 0)),
    },
    # Colour sequences per slot along the repeats.
    "palette-sequences": {
        "unit_width": 4,
        "unit_height": 4,
        "repeats_x": 5,
        "repeats_y": 2,
        "repeat_left_column": False,
        "repeat_right_column": False,
        "repeat_top_row": False,
        "repeat_bottom_row": False,
        "use_palette_sequence": True,
        "background": "#ffffff",
        "palette_sequences": [
            ["#ff0000", "#00ff00", "#0000ff"],
            ["#111111"],
            ["#aaaaaa", "#bbbbbb"],
        ],
        "symmetry": ["identity", "rotate_180"],
        "motif": _marks((0, 0, 0), (1, 1, 1), (2, 1, 2), (0, 3, 5)),
        "backstitches": _stitches((0, 0, 4, 4, 0), (1, 2, 2, 2, 2)),
    },
    # One end piece per edge, each with removed and added cells, backstitch
    # changes and a non-zero extension.
    "end-pieces": {
        "unit_width": 6,
        "unit_height": 6,
        "repeats_x": 3,
        "repeats_y": 3,
        "background": "#ffffff",
        "use_palette_sequence": True,
        "palette_sequences": [["#b1172b", "#123456"], ["#2d7d32"], ["#f2c84b"], ["#1b1b1b"]],
        "symmetry": ["identity", "mirror_x"],
        "motif": _marks((0, 0, 0), (1, 1, 1), (2, 2, 2), (1, 5, 3)),
        "backstitches": _stitches((0, 3, 2, 3, 3), (1, 0, 1, 1, 0)),
        "top_repeat_override": {
            "removed_cells": _cells((0, 0), (4, 1)),
            "added_marks": _marks((2, -1, 1), (5, -2, 0), (3, 3, 2)),
            "removed_backstitches": _keys((0, 3, 2, 3)),
            "added_backstitches": _stitches((0, -2, 3, -1, 3), (2, 0, 2, 2, 1)),
            "extension": 2,
        },
        "bottom_repeat_override": {
            "removed_cells": _cells((1, 5), (4, 5)),
            "added_marks": _marks((0, 6, 2), (5, 7, 3), (2, 4, 0)),
            "removed_backstitches": _keys((1, 0, 1, 1)),
            "added_backstitches": _stitches((0, 6, 6, 8, 2),),
            "extension": 3,
        },
        "left_repeat_override": {
            "removed_cells": _cells((0, 0), (1, 1)),
            "added_marks": _marks((-1, 0, 1), (-1, 5, 2), (3, 0, 3)),
            "removed_backstitches": _keys((4, 3, 6, 3)),
            "added_backstitches": _stitches((-1, 0, 0, 6, 1),),
            "extension": 1,
        },
        "right_repeat_override": {
            "removed_cells": _cells((5, 0), (2, 2)),
            "added_marks": _marks((6, 0, 0), (7, 3, 1), (2, 2, 3)),
            "removed_backstitches": _keys((4, 0, 4, 1)),
            "added_backstitches": _stitches((6, 0, 8, 6, 0),),
            "extension": 2,
        },
    },
    # End pieces on a single repeat with outer rows/columns not repeated, so
    # every override applies to the same unit.
    "end-pieces-single-repeat": {
        "unit_width": 5,
        "unit_height": 4,
        "repeats_x": 1,
        "repeats_y": 1,
        "repeat_left_column": False,
        "repeat_right_column": False,
        "repeat_top_row": False,
        "repeat_bottom_row": False,
        "background": "#eeeeee",
        "palette_sequences": _BASE_PALETTE,
        "symmetry": ["identity", "mirror_y"],
        "motif": _marks((0, 0, 0), (2, 1, 1), (4, 0, 2)),
        "backstitches": _stitches((0, 0, 5, 0, 3),),
        "top_repeat_override": {
            "removed_cells": _cells((2, 1),),
            "added_marks": _marks((1, -1, 3),),
            "extension": 1,
        },
        "bottom_repeat_override": {
            "added_marks": _marks((3, 4, 1), (3, 3, 0)),
            "removed_backstitches": _keys((0, 4, 5, 4)),
            "extension": 1,
        },
        "left_repeat_override": {
            "added_marks": _marks((-2, 1, 2),),
            "added_backstitches": _stitches((-2, 0, -2, 4, 0),),
            "extension": 2,
        },
        "right_repeat_override": {
            "removed_cells": _cells((4, 0), (4, 3)),
            "extension": 0,
        },
    },
    # End pieces combined with outer columns/rows that are not repeated.
    "end-pieces-edges": {
        "unit_width": 4,
        "unit_height": 4,
        "repeats_x": 4,
        "repeats_y": 2,
        "repeat_left_column": False,
        "repeat_right_column": True,
        "repeat_top_row": False,
        "repeat_bottom_row": True,
        "background": "#ffffff",
        "palette_sequences": _BASE_PALETTE,
        "symmetry": ["identity", "rotate_90"],
        "motif": _marks((0, 0, 0), (1, 0, 1), (3, 2, 2)),
        "backstitches": _stitches((0, 0, 1, 0, 3), (0, 4, 4, 0, 1)),
        "left_repeat_override": {
            "removed_cells": _cells((0, 0),),
            "added_marks": _marks((-1, 1, 3), (-3, 3, 2)),
            "added_backstitches": _stitches((-3, 0, 0, 0, 2),),
            "extension": 3,
        },
        "top_repeat_override": {
            "removed_cells": _cells((1, 0),),
            "added_marks": _marks((0, -1, 1),),
            "removed_backstitches": _keys((0, 0, 1, 0)),
            "extension": 1,
        },
    },
}
