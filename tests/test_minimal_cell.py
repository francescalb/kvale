"""The minimal cell: the part of the unit the user edits under symmetry."""

from __future__ import annotations

import itertools

import pytest

from kvale.core.model import Backstitch, Mark
from kvale.core.symmetry import (
    SUPPORTED_OPERATIONS,
    backstitch_in_minimal_cell,
    expand_backstitches,
    expand_marks,
    minimal_cell,
    normalise_symmetry,
)

Cells = frozenset[tuple[int, int]]

SIZES = [(1, 1), (2, 2), (5, 5), (6, 6), (7, 7), (8, 8), (6, 4), (7, 4), (4, 7), (5, 3)]
COMBINATIONS = [
    combination
    for count in range(len(SUPPORTED_OPERATIONS))
    for combination in itertools.combinations(SUPPORTED_OPERATIONS[1:], count)
]
# Backstitch checks are slower, so they use fewer sizes.
BACKSTITCH_SIZES = [(2, 2), (5, 5), (6, 6), (6, 4), (5, 3)]


def _cases(sizes: list[tuple[int, int]]) -> list[object]:
    return [
        pytest.param(width, height, combination, id=f"{width}x{height}-{'+'.join(combination) or 'identity'}")
        for width, height in sizes
        for combination in COMBINATIONS
    ]


CASES = _cases(SIZES)
BACKSTITCH_CASES = _cases(BACKSTITCH_SIZES)


def _orbit(cell: tuple[int, int], width: int, height: int, operations: list[str]) -> set[tuple[int, int]]:
    return {(mark.x, mark.y) for mark in expand_marks([Mark(*cell, 0)], width, height, operations)}


def _shape(cells: Cells, width: int, height: int) -> list[str]:
    return ["".join("#" if (x, y) in cells else "." for x in range(width)) for y in range(height)]


def _connected(cells: Cells) -> bool:
    if not cells:
        return True
    start = next(iter(cells))
    seen = {start}
    pending = [start]
    while pending:
        x, y = pending.pop()
        for neighbour in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if neighbour in cells and neighbour not in seen:
                seen.add(neighbour)
                pending.append(neighbour)
    return seen == set(cells)


@pytest.mark.parametrize(("width", "height", "combination"), CASES)
def test_minimal_cell_holds_each_orbit_once_and_fills_the_unit(
    width: int, height: int, combination: tuple[str, ...]
) -> None:
    operations, _removed = normalise_symmetry(combination, width, height)
    cells = minimal_cell(width, height, combination)
    unit = {(x, y) for x in range(width) for y in range(height)}
    assert cells <= unit

    # Exactly one cell of every orbit.
    for cell in unit:
        assert len(_orbit(cell, width, height, operations) & cells) == 1, cell

    # Expanding the minimal cell fills the whole unit.
    expanded = expand_marks([Mark(x, y, 0) for x, y in cells], width, height, operations)
    assert {(mark.x, mark.y) for mark in expanded} == unit

    assert _connected(cells), _shape(cells, width, height)
    assert (0, 0) in cells


@pytest.mark.parametrize(("width", "height", "combination"), BACKSTITCH_CASES)
def test_every_backstitch_orbit_has_an_editable_member(
    width: int, height: int, combination: tuple[str, ...]
) -> None:
    operations, _removed = normalise_symmetry(combination, width, height)
    cells = minimal_cell(width, height, combination)
    points = [(x, y) for x in range(width + 1) for y in range(height + 1)]
    # Every grid-line step and cell diagonal, plus a few longer stitches, in
    # all directions so that the list holds every symmetric copy.
    steps = {
        (sx * a, sy * b)
        for first, second in ((1, 0), (1, 1), (2, 1), (3, 0))
        for a, b in ((first, second), (second, first))
        for sx in (1, -1)
        for sy in (1, -1)
    }
    stitches = [
        (start, (start[0] + dx, start[1] + dy))
        for start in points
        for dx, dy in sorted(steps)
        if 0 <= start[0] + dx <= width and 0 <= start[1] + dy <= height
    ]
    editable = [
        Backstitch(*start, *end, 0)
        for start, end in stitches
        if backstitch_in_minimal_cell(start, end, cells)
    ]
    # The symmetric copies of the editable stitches include every stitch.
    expanded = {stitch.key for stitch in expand_backstitches(editable, width, height, operations)}
    for start, end in stitches:
        assert Backstitch(*start, *end, 0).key in expanded, (start, end)

@pytest.mark.parametrize(
    ("width", "height", "operations", "shape"),
    [
        (4, 3, ["identity"], ["####", "####", "####"]),
        (6, 2, ["mirror_x"], ["###...", "###..."]),
        (5, 5, ["mirror_x", "mirror_y"], ["###..", "###..", "###..", ".....", "....."]),
        (4, 4, ["rotate_180"], ["####", "####", "....", "...."]),
        (5, 3, ["rotate_180"], ["#####", "###..", "....."]),
        (4, 4, ["rotate_90"], ["##..", "##..", "....", "...."]),
        (5, 5, ["rotate_90"], ["###..", "###..", "..#..", ".....", "....."]),
        (4, 4, ["diag_main"], ["####", ".###", "..##", "...#"]),
        (4, 4, ["diag_anti"], ["####", "###.", "##..", "#..."]),
        (5, 5, SUPPORTED_OPERATIONS, ["###..", ".##..", "..#..", ".....", "....."]),
        # Square-only operations are ignored on a non-square unit.
        (4, 2, ["rotate_90", "mirror_x"], ["##..", "##.."]),
    ],
)
def test_minimal_cell_shapes(
    width: int, height: int, operations: list[str], shape: list[str]
) -> None:
    assert _shape(minimal_cell(width, height, operations), width, height) == shape


def test_backstitch_on_mirror_axis_and_outline_is_editable() -> None:
    cells = minimal_cell(6, 4, ["mirror_x"])  # columns 0-2
    assert backstitch_in_minimal_cell((3, 0), (3, 1), cells)  # mirror axis
    assert backstitch_in_minimal_cell((0, 0), (1, 0), cells)  # top outline
    assert backstitch_in_minimal_cell((2, 1), (3, 2), cells)  # diagonal inside
    assert not backstitch_in_minimal_cell((4, 0), (4, 1), cells)
    assert not backstitch_in_minimal_cell((3, 1), (4, 2), cells)
    assert backstitch_in_minimal_cell((3, 1), (4, 2), minimal_cell(6, 4, []))
