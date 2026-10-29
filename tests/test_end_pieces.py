"""Tests for end pieces, backstitches and grid changes in kvale.core.editing."""

import subprocess
import sys

from kvale.core.editing import (
    add_backstitch,
    add_end_piece_backstitch,
    can_remove_grid_line,
    change_grid_line,
    editor_bounds,
    erase_backstitch_near,
    erase_end_piece_cell,
    find_backstitch_near,
    get_end_piece,
    grid_line_for_place,
    hidden_backstitches,
    max_line_number,
    paint_cell,
    paint_end_piece_cell,
    reset_end_piece,
    resize_unit,
    set_end_piece_extension,
    visible_backstitches,
)
from kvale.core.editor import Editor
from kvale.core.model import (
    Backstitch,
    BackstitchKey,
    Cell,
    Mark,
    PatternDocument,
    RepeatOverride,
)
from kvale.core.renderer import build_colour_grid


def _document() -> PatternDocument:
    return PatternDocument(
        unit_width=4,
        unit_height=4,
        repeats_x=2,
        repeats_y=2,
        symmetry=["identity", "mirror_x"],
        motif=[Mark(0, 0, 1)],
        backstitches=[Backstitch(0, 1, 1, 1, 2)],
    )


def test_paint_cell_with_same_colour_does_nothing() -> None:
    document = _document()

    assert not paint_cell(document, 3, 0, 1)  # mirrored copy, same colour
    assert paint_cell(document, 3, 0, 2)
    assert document.motif == [Mark(0, 0, 2)]


def test_end_piece_paint_adds_and_restores() -> None:
    document = _document()

    assert not paint_end_piece_cell(document, "top", 3, 0, 1)  # already that colour
    assert get_end_piece(document, "top") is None

    assert paint_end_piece_cell(document, "top", 3, 0, 3)
    assert get_end_piece(document, "top") == RepeatOverride(added_marks=[Mark(3, 0, 3)])

    assert paint_end_piece_cell(document, "top", 3, 0, 1)  # back to the unit colour
    assert get_end_piece(document, "top") == RepeatOverride()


def test_end_piece_erase_hides_unit_cell_and_paint_restores_it() -> None:
    document = _document()

    assert erase_end_piece_cell(document, "left", 0, 0)
    assert get_end_piece(document, "left") == RepeatOverride(removed_cells=[Cell(0, 0)])
    assert not erase_end_piece_cell(document, "left", 0, 0)  # already hidden
    assert not erase_end_piece_cell(document, "left", 1, 1)  # empty cell

    assert paint_end_piece_cell(document, "left", 0, 0, 1)
    assert get_end_piece(document, "left") == RepeatOverride()


def test_end_piece_outside_bounds_is_ignored() -> None:
    document = _document()

    assert not paint_end_piece_cell(document, "top", 0, -1, 0)
    assert set_end_piece_extension(document, "top", 2)
    assert editor_bounds(document, "top") == (0, 3, -2, 3)
    assert paint_end_piece_cell(document, "top", 0, -1, 0)
    assert not paint_end_piece_cell(document, "top", 0, -3, 0)
    assert not paint_end_piece_cell(document, "top", 4, 0, 0)


def test_extension_trims_added_marks_and_backstitches() -> None:
    document = _document()
    set_end_piece_extension(document, "right", 3)
    paint_end_piece_cell(document, "right", 6, 1, 0)
    paint_end_piece_cell(document, "right", 4, 1, 0)
    add_end_piece_backstitch(document, "right", (4, 0), (7, 0), 0)
    add_end_piece_backstitch(document, "right", (4, 0), (5, 0), 1)

    assert not set_end_piece_extension(document, "right", 3)
    assert set_end_piece_extension(document, "right", 1)

    override = get_end_piece(document, "right")
    assert override is not None
    assert override.added_marks == [Mark(4, 1, 0)]
    assert override.added_backstitches == [Backstitch(4, 0, 5, 0, 1)]
    assert not set_end_piece_extension(document, "left", -4)  # raised to 0: no change


def test_end_piece_extension_is_rendered() -> None:
    document = _document()
    set_end_piece_extension(document, "bottom", 1)
    paint_end_piece_cell(document, "bottom", 1, 4, 3)

    grid = build_colour_grid(document)

    assert len(grid) == 9
    colour = document.palette[3]
    assert [x for x, value in enumerate(grid[8]) if value == colour] == [1, 5]


def test_reset_end_piece() -> None:
    document = _document()
    assert not reset_end_piece(document, "bottom")
    set_end_piece_extension(document, "bottom", 1)
    assert reset_end_piece(document, "bottom")
    assert document.bottom_repeat_override is None


def test_unit_backstitch_add_recolour_and_erase() -> None:
    document = _document()

    assert not add_backstitch(document, (2, 2), (2, 2), 0)
    assert not add_backstitch(document, (0, 0), (5, 0), 0)  # outside the unit
    assert not add_backstitch(document, (4, 1), (3, 1), 2)  # mirrored copy, same colour
    assert add_backstitch(document, (4, 1), (3, 1), 3)  # recolours the stored stitch
    assert document.backstitches == [Backstitch(0, 1, 1, 1, 3)]

    assert visible_backstitches(document) == [
        Backstitch(0, 1, 1, 1, 3),
        Backstitch(4, 1, 3, 1, 3),
    ]
    assert find_backstitch_near(document, 2.0, 2.0) is None
    assert erase_backstitch_near(document, 3.5, 1.1)
    assert document.backstitches == []


def test_end_piece_backstitch_hide_recolour_restore() -> None:
    document = _document()
    key = BackstitchKey(3, 1, 4, 1)

    assert not add_end_piece_backstitch(document, "top", (4, 1), (3, 1), 2)
    assert add_end_piece_backstitch(document, "top", (4, 1), (3, 1), 0)
    assert add_end_piece_backstitch(document, "top", (4, 1), (3, 1), 2)  # restores
    override = get_end_piece(document, "top")
    assert override == RepeatOverride()

    assert erase_backstitch_near(document, 3.5, 1.0, "top")
    assert get_end_piece(document, "top") == RepeatOverride(removed_backstitches=[key])
    assert hidden_backstitches(document, "top") == [Backstitch(4, 1, 3, 1, 2)]
    assert visible_backstitches(document, "top") == [Backstitch(0, 1, 1, 1, 2)]
    # The unit is unchanged.
    assert document.backstitches == [Backstitch(0, 1, 1, 1, 2)]


def test_change_grid_line_follows_symmetry_and_moves_end_pieces() -> None:
    document = _document()
    set_end_piece_extension(document, "right", 1)
    paint_end_piece_cell(document, "right", 4, 2, 0)
    erase_end_piece_cell(document, "right", 3, 0)

    # mirror_x ties column 0 to column 3: both are removed.
    assert can_remove_grid_line(document, "column", 0)
    assert change_grid_line(document, "column", 0, insertion=False) == []

    assert document.unit_width == 2
    assert document.motif == []
    assert document.backstitches == []  # (0,1)-(1,1) collapsed to one point
    override = get_end_piece(document, "right")
    assert override is not None
    assert override.added_marks == [Mark(2, 2, 0)]
    assert override.removed_cells == []

    assert change_grid_line(document, "column", 1, insertion=True) == []
    assert document.unit_width == 3  # the middle gap is its own mirror image
    assert override.added_marks == [Mark(3, 2, 0)]


def test_cannot_remove_the_last_lines() -> None:
    document = PatternDocument(unit_width=2, unit_height=3, symmetry=["identity", "mirror_x"])

    assert not can_remove_grid_line(document, "column", 0)
    assert change_grid_line(document, "column", 0, insertion=False) == []
    assert document.unit_width == 2


def test_grid_line_for_place() -> None:
    document = PatternDocument(unit_width=5, unit_height=3)

    assert grid_line_for_place(document, "top_row", insertion=True) == ("row", 0)
    assert grid_line_for_place(document, "bottom_row", insertion=True) == ("row", 3)
    assert grid_line_for_place(document, "bottom_row", insertion=False) == ("row", 2)
    assert grid_line_for_place(document, "first_column", insertion=False) == ("column", 0)
    assert grid_line_for_place(document, "last_column", insertion=True) == ("column", 5)
    assert grid_line_for_place(document, "last_column", insertion=False) == ("column", 4)
    assert grid_line_for_place(document, "row", insertion=False, number=2) == ("row", 1)
    assert grid_line_for_place(document, "column", insertion=True, number=6) == ("column", 5)
    assert max_line_number(document, "row", insertion=True) == 4
    assert max_line_number(document, "column", insertion=False) == 5


def test_resize_unit_moves_bottom_and_right_extensions() -> None:
    document = _document()
    set_end_piece_extension(document, "bottom", 1)
    paint_end_piece_cell(document, "bottom", 1, 4, 2)
    add_end_piece_backstitch(document, "bottom", (0, 5), (1, 4), 2)
    erase_end_piece_cell(document, "bottom", 0, 0)

    resize_unit(document, 3, 6)

    override = get_end_piece(document, "bottom")
    assert override is not None
    assert override.added_marks == [Mark(1, 6, 2)]
    assert override.added_backstitches == [Backstitch(0, 7, 1, 6, 2)]
    assert override.removed_cells == [Cell(0, 0)]
    assert document.backstitches == [Backstitch(0, 1, 1, 1, 2)]

    resize_unit(document, 1, 6)
    assert document.backstitches == [Backstitch(0, 1, 1, 1, 2)]
    assert override.added_marks == []


def test_editor_end_piece_and_backstitch_steps_undo() -> None:
    editor = Editor(_document())

    assert editor.paint(3, 0, 3, target="top").changed
    assert editor.erase(0, 0, target="left").changed
    assert editor.set_end_piece_extension("bottom", 2).changed
    assert editor.add_backstitch((0, 0), (1, 0), 1).changed
    assert editor.add_backstitch((0, 0), (1, 0), 3, target="right").changed
    assert editor.erase_backstitch_near(0.5, 1.0).changed
    assert not editor.erase_backstitch_near(2.0, 2.5).changed
    assert editor.reset_end_piece("bottom").changed
    assert not editor.reset_end_piece("bottom").changed

    steps = 0
    while editor.undo():
        steps += 1
    assert steps == 7
    assert editor.document == _document()


def test_importing_core_does_not_import_pillow() -> None:
    code = "import sys, kvale.core, kvale.core.editing, kvale.core.dmc; print('PIL' in sys.modules)"
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "False"
