"""Tests for the corner end pieces (top_left, top_right, bottom_left, bottom_right)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from kvale.core.editing import (
    CORNERS,
    add_end_piece_backstitch,
    base_marks,
    change_grid_line,
    editor_bounds,
    erase_backstitch_near,
    erase_end_piece_cell,
    get_end_piece,
    hidden_backstitches,
    intersection_in_editor,
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
from kvale.core.renderer import RenderedBackstitch, build_backstitch_segments, build_colour_grid
from kvale.core.serialization import load_document, save_document

ROOT = Path(__file__).resolve().parent.parent
BACKGROUND = "#ffffff"


def _document() -> PatternDocument:
    """A 4x4 unit repeated 3 across and 2 down, with one mark and one backstitch."""
    return PatternDocument(
        unit_width=4,
        unit_height=4,
        repeats_x=3,
        repeats_y=2,
        motif=[Mark(0, 0, 1)],
        backstitches=[Backstitch(0, 1, 1, 1, 2)],
    )


def _extended() -> PatternDocument:
    """_document() with one extra row/column on every edge."""
    document = _document()
    document.top_repeat_override = RepeatOverride(extension=1)
    document.bottom_repeat_override = RepeatOverride(extension=1)
    document.left_repeat_override = RepeatOverride(extension=1)
    document.right_repeat_override = RepeatOverride(extension=1)
    return document


# Model --------------------------------------------------------------------


def test_new_document_has_no_corners() -> None:
    document = PatternDocument()
    for corner in CORNERS:
        assert get_end_piece(document, corner) is None
    assert not document.has_corner_overrides()


def test_corner_bounds_follow_neighbouring_extensions() -> None:
    document = _document()
    document.top_repeat_override = RepeatOverride(extension=2)
    document.left_repeat_override = RepeatOverride(extension=1)
    document.right_repeat_override = RepeatOverride(extension=3)

    assert document.corner_bounds("top_left") == (-1, 3, -2, 3)
    assert document.corner_bounds("top_right") == (0, 6, -2, 3)
    assert document.corner_bounds("bottom_left") == (-1, 3, 0, 3)
    assert document.corner_bounds("bottom_right") == (0, 6, 0, 3)
    assert editor_bounds(document, "top_left") == (-1, 3, -2, 3)


def test_corner_validation_allows_crossing_square() -> None:
    document = _extended()
    document.top_left_repeat_override = RepeatOverride(
        removed_cells=[Cell(-1, 2)],
        added_marks=[Mark(-1, -1, 2)],
        removed_backstitches=[BackstitchKey.between(-1, -1, 0, -1)],
        added_backstitches=[Backstitch(-1, -1, 0, 0, 1)],
    )
    document.bottom_right_repeat_override = RepeatOverride(
        added_marks=[Mark(4, 4, 2)], added_backstitches=[Backstitch(4, 4, 5, 5, 1)]
    )
    document.validate()


@pytest.mark.parametrize(
    "override",
    [
        RepeatOverride(added_marks=[Mark(-1, -1, 0)]),  # no extensions yet
        RepeatOverride(removed_cells=[Cell(0, -1)]),
        RepeatOverride(added_backstitches=[Backstitch(0, 0, -1, 0)]),
        RepeatOverride(removed_backstitches=[BackstitchKey(0, -1, 1, -1)]),
        RepeatOverride(extension=1),  # a corner has no extension of its own
    ],
)
def test_corner_validation_rejects_outside_region(override: RepeatOverride) -> None:
    document = _document()
    document.top_left_repeat_override = override
    with pytest.raises(ValueError):
        document.validate()


def test_corner_validation_rejects_other_sides() -> None:
    document = _extended()
    document.top_left_repeat_override = RepeatOverride(added_marks=[Mark(4, 0, 0)])  # right side
    with pytest.raises(ValueError):
        document.validate()
    document.top_left_repeat_override = RepeatOverride(added_marks=[Mark(-2, 0, 0)])  # too far
    with pytest.raises(ValueError):
        document.validate()


def test_edge_validation_still_rejects_crossing_square() -> None:
    document = _extended()
    document.top_repeat_override = RepeatOverride(extension=1, added_marks=[Mark(-1, -1, 0)])
    with pytest.raises(ValueError):
        document.validate()


# Renderer: cells ----------------------------------------------------------


def test_corner_mark_fills_crossing_square() -> None:
    document = _extended()
    before = build_colour_grid(document)
    document.top_left_repeat_override = RepeatOverride(added_marks=[Mark(-1, -1, 2)])
    document.bottom_right_repeat_override = RepeatOverride(added_marks=[Mark(4, 4, 3)])

    grid = build_colour_grid(document)

    assert len(grid) == 1 + 8 + 1 and len(grid[0]) == 1 + 12 + 1
    assert grid[0][0] == document.palette[2]
    assert grid[9][13] == document.palette[3]
    changed = {
        (x, y) for y, row in enumerate(grid) for x, value in enumerate(row) if value != before[y][x]
    }
    assert changed == {(0, 0), (13, 9)}


def test_corner_changes_only_the_corner_unit() -> None:
    document = _extended()
    document.top_left_repeat_override = RepeatOverride(removed_cells=[Cell(0, 0)])
    document.top_right_repeat_override = RepeatOverride(added_marks=[Mark(3, 3, 2)])

    grid = build_colour_grid(document)

    colour = document.palette[1]
    # Unit (0, 0) starts at grid (1, 1); the others along the top at x = 5 and 9.
    assert grid[1][1] == BACKGROUND
    assert grid[1][5] == colour and grid[1][9] == colour
    assert grid[5][1] == colour  # unit (0, 1) is not a corner of the top row
    assert grid[4][12] == document.palette[2]
    assert grid[4][4] == BACKGROUND and grid[4][8] == BACKGROUND


def test_corner_is_applied_after_both_edges() -> None:
    document = _extended()
    top = document.top_repeat_override
    left = document.left_repeat_override
    assert top is not None and left is not None
    top.added_marks = [Mark(2, -1, 3)]
    left.added_marks = [Mark(0, 0, 2)]
    document.top_left_repeat_override = RepeatOverride(
        removed_cells=[Cell(2, -1)], added_marks=[Mark(0, 0, 3)]
    )

    grid = build_colour_grid(document)

    assert grid[0][3] == BACKGROUND  # the corner hides the top edge's mark
    assert grid[0][7] == document.palette[3]  # the next unit keeps it
    assert grid[1][1] == document.palette[3]  # the corner wins over the left edge
    assert grid[5][1] == document.palette[2]  # the left edge below the corner


def test_corner_uses_edge_toggles() -> None:
    document = _document()
    document.repeat_left_column = False
    document.repeat_right_column = False
    document.top_right_repeat_override = RepeatOverride(
        added_marks=[Mark(0, 1, 2), Mark(3, 1, 3)]
    )

    grid = build_colour_grid(document)

    # Columns: unit 0 keeps 0..2 (3), unit 1 keeps 1..2 (2), unit 2 keeps 1..3 (3).
    assert len(grid[0]) == 8
    assert grid[1][7] == document.palette[3]
    assert document.palette[2] not in grid[1]  # its left column is not drawn


def test_one_unit_band_gets_all_corners() -> None:
    document = PatternDocument(unit_width=2, unit_height=2, repeats_x=1, repeats_y=1)
    for slot, corner in enumerate(CORNERS):
        setattr(document, f"{corner}_repeat_override", RepeatOverride(added_marks=[Mark(0, 0, slot)]))
    assert build_colour_grid(document)[0][0] == document.palette[3]  # bottom_right is last


# Renderer: backstitches ---------------------------------------------------


def test_corner_backstitch_in_crossing_square() -> None:
    document = _extended()
    before = build_backstitch_segments(document)
    document.top_left_repeat_override = RepeatOverride(
        added_backstitches=[Backstitch(-1, -1, 0, 0, 1)]
    )
    document.bottom_left_repeat_override = RepeatOverride(
        added_backstitches=[Backstitch(-1, 5, 0, 4, 3)]
    )

    segments = build_backstitch_segments(document)

    added = [segment for segment in segments if segment not in before]
    assert added == [
        RenderedBackstitch(0, 0, 1, 1, document.palette[1]),
        RenderedBackstitch(0, 10, 1, 9, document.palette[3]),
    ]


def test_corner_hides_backstitch_in_corner_unit_only() -> None:
    document = _extended()
    document.top_left_repeat_override = RepeatOverride(
        removed_backstitches=[BackstitchKey(0, 1, 1, 1)]
    )

    segments = build_backstitch_segments(document)

    colour = document.palette[2]
    assert RenderedBackstitch(1, 2, 2, 2, colour) not in segments
    assert RenderedBackstitch(5, 2, 6, 2, colour) in segments
    assert RenderedBackstitch(1, 6, 2, 6, colour) in segments


# Editing ------------------------------------------------------------------


def test_paint_and_erase_corner_cells() -> None:
    document = _document()
    assert not paint_end_piece_cell(document, "top_left", -1, -1, 2)  # no extensions yet
    set_end_piece_extension(document, "top", 1)
    set_end_piece_extension(document, "left", 1)

    assert paint_end_piece_cell(document, "top_left", -1, -1, 2)
    assert not paint_end_piece_cell(document, "top_left", -1, -1, 2)
    assert not paint_end_piece_cell(document, "top_left", 0, 0, 1)  # already that colour
    assert erase_end_piece_cell(document, "top_left", 0, 0)
    assert get_end_piece(document, "top_left") == RepeatOverride(
        removed_cells=[Cell(0, 0)], added_marks=[Mark(-1, -1, 2)]
    )
    assert erase_end_piece_cell(document, "top_left", -1, -1)
    assert not erase_end_piece_cell(document, "top_left", -1, -1)
    assert paint_end_piece_cell(document, "top_left", 0, 0, 1)  # restores the unit cell
    assert get_end_piece(document, "top_left") == RepeatOverride()
    document.validate()


def test_corner_starts_from_edge_end_pieces() -> None:
    document = _document()
    set_end_piece_extension(document, "top", 1)
    paint_end_piece_cell(document, "top", 2, -1, 3)
    erase_end_piece_cell(document, "left", 0, 0)

    assert base_marks(document, "top_left") == {(2, -1): Mark(2, -1, 3)}
    assert base_marks(document, "top") == {(0, 0): Mark(0, 0, 1)}

    # Hiding a cell the top edge added, then painting it back in the same colour.
    assert erase_end_piece_cell(document, "top_left", 2, -1)
    assert get_end_piece(document, "top_left") == RepeatOverride(removed_cells=[Cell(2, -1)])
    assert paint_end_piece_cell(document, "top_left", 2, -1, 3)
    assert get_end_piece(document, "top_left") == RepeatOverride()
    assert not erase_end_piece_cell(document, "top_left", 0, 0)  # hidden by the left edge
    document.validate()


def test_corner_backstitches() -> None:
    document = _document()
    set_end_piece_extension(document, "bottom", 1)
    set_end_piece_extension(document, "right", 1)
    add_end_piece_backstitch(document, "right", (4, 0), (5, 0), 3)

    assert intersection_in_editor(document, "bottom_right", 5, 5)
    assert not intersection_in_editor(document, "bottom_right", -1, 0)
    assert add_end_piece_backstitch(document, "bottom_right", (4, 4), (5, 5), 1)
    assert not add_end_piece_backstitch(document, "bottom_right", (4, 0), (5, 0), 3)
    assert {item.key for item in visible_backstitches(document, "bottom_right")} == {
        BackstitchKey(0, 1, 1, 1),
        BackstitchKey(4, 0, 5, 0),
        BackstitchKey(4, 4, 5, 5),
    }

    assert erase_backstitch_near(document, 4.5, 0.0, "bottom_right")  # hides the edge's stitch
    override = get_end_piece(document, "bottom_right")
    assert override == RepeatOverride(
        removed_backstitches=[BackstitchKey(4, 0, 5, 0)],
        added_backstitches=[Backstitch(4, 4, 5, 5, 1)],
    )
    assert hidden_backstitches(document, "bottom_right") == [Backstitch(4, 0, 5, 0, 3)]
    assert add_end_piece_backstitch(document, "bottom_right", (4, 0), (5, 0), 3)  # restores
    assert erase_backstitch_near(document, 4.5, 4.5, "bottom_right")  # removes the added one
    assert get_end_piece(document, "bottom_right") == RepeatOverride()
    document.validate()


def test_shrinking_an_edge_trims_its_corners() -> None:
    document = _document()
    set_end_piece_extension(document, "top", 2)
    set_end_piece_extension(document, "left", 2)
    paint_end_piece_cell(document, "top_left", -2, -2, 2)
    paint_end_piece_cell(document, "top_left", -1, -1, 2)
    paint_end_piece_cell(document, "top_left", 3, -2, 2)
    add_end_piece_backstitch(document, "top_left", (-2, -2), (0, 0), 1)
    add_end_piece_backstitch(document, "top_left", (-1, -1), (0, 0), 1)
    add_end_piece_backstitch(document, "top_right", (0, -2), (1, -2), 1)
    top_left = get_end_piece(document, "top_left")
    assert top_left is not None
    top_left.removed_cells.append(Cell(-2, 0))

    assert set_end_piece_extension(document, "top", 1)

    assert top_left.added_marks == [Mark(-1, -1, 2)]
    assert top_left.added_backstitches == [Backstitch(-1, -1, 0, 0, 1)]
    assert top_left.removed_cells == [Cell(-2, 0)]
    assert get_end_piece(document, "top_right") == RepeatOverride()
    document.validate()

    assert reset_end_piece(document, "left")  # removes the left extension too
    assert top_left.added_marks == []
    assert top_left.added_backstitches == []
    assert top_left.removed_cells == []
    document.validate()


def test_reset_corner() -> None:
    document = _document()
    assert not reset_end_piece(document, "top_left")
    erase_end_piece_cell(document, "top_left", 0, 0)
    assert reset_end_piece(document, "top_left")
    assert document.top_left_repeat_override is None


def test_resize_moves_far_corner_content() -> None:
    document = _extended()
    paint_end_piece_cell(document, "bottom_right", 4, 4, 2)
    paint_end_piece_cell(document, "bottom_right", 1, 4, 2)
    add_end_piece_backstitch(document, "bottom_right", (4, 4), (5, 5), 1)
    paint_end_piece_cell(document, "top_left", -1, -1, 2)
    erase_end_piece_cell(document, "bottom_right", 0, 0)

    resize_unit(document, 6, 3)

    bottom_right = get_end_piece(document, "bottom_right")
    assert bottom_right is not None
    assert bottom_right.added_marks == [Mark(6, 3, 2), Mark(1, 3, 2)]
    assert bottom_right.added_backstitches == [Backstitch(6, 3, 7, 4, 1)]
    assert bottom_right.removed_cells == [Cell(0, 0)]
    assert get_end_piece(document, "top_left") == RepeatOverride(added_marks=[Mark(-1, -1, 2)])
    document.validate()


def test_grid_line_change_moves_corner_content() -> None:
    document = _extended()
    paint_end_piece_cell(document, "top_right", 4, -1, 2)
    paint_end_piece_cell(document, "top_right", 2, 2, 3)

    change_grid_line(document, "column", 1, insertion=True)

    assert get_end_piece(document, "top_right") == RepeatOverride(
        added_marks=[Mark(5, -1, 2), Mark(3, 2, 3)]
    )
    document.validate()


def test_editor_corner_steps_undo_and_redo() -> None:
    editor = Editor(_document())

    assert editor.set_end_piece_extension("top", 1).changed
    assert editor.set_end_piece_extension("left", 1).changed
    assert editor.paint(-1, -1, 2, target="top_left").changed
    assert editor.erase(0, 0, target="top_left").changed
    assert editor.add_backstitch((-1, -1), (0, 0), 1, target="top_left").changed
    assert editor.erase_backstitch_near(0.5, 1.0, target="top_left").changed
    assert not editor.paint(-1, -1, 2, target="top_left").changed
    with_corner = copy.deepcopy(editor.document)
    assert editor.reset_end_piece("top_left").changed
    assert not editor.reset_end_piece("top_left").changed
    assert editor.document.top_left_repeat_override is None

    assert editor.undo()
    assert editor.document == with_corner
    steps = 1
    while editor.undo():
        steps += 1
    assert steps == 7
    assert editor.document == _document()
    while editor.redo():
        pass
    assert editor.document.top_left_repeat_override is None
    assert editor.document.top_repeat_override == RepeatOverride(extension=1)


# Serialization ------------------------------------------------------------


def test_to_dict_without_corners_has_no_corner_keys() -> None:
    data = _extended().to_dict()
    assert data["format_version"] == 4
    assert not any(f"{corner}_repeat_override" in data for corner in CORNERS)


def test_corner_round_trip(tmp_path: Path) -> None:
    document = _extended()
    document.top_left_repeat_override = RepeatOverride(
        removed_cells=[Cell(0, 0)],
        added_marks=[Mark(-1, -1, 2)],
        removed_backstitches=[BackstitchKey(0, 1, 1, 1)],
        added_backstitches=[Backstitch(-1, -1, 0, 0, 1)],
    )
    document.bottom_right_repeat_override = RepeatOverride(added_marks=[Mark(4, 4, 3)])

    data = document.to_dict()
    assert data["format_version"] == 5
    assert "top_left_repeat_override" in data
    assert "top_right_repeat_override" not in data
    assert list(data)[-2:] == ["top_left_repeat_override", "bottom_right_repeat_override"]

    path = tmp_path / "corners.json"
    save_document(document, path)
    assert json.loads(path.read_text())["format_version"] == 5
    restored = load_document(path)
    assert restored == document
    assert build_colour_grid(restored) == build_colour_grid(document)
    assert build_backstitch_segments(restored) == build_backstitch_segments(document)


def test_old_files_load_without_corners() -> None:
    document = load_document(ROOT / "examples" / "flower-band.json")
    assert not document.has_corner_overrides()


def test_newer_format_is_rejected() -> None:
    data = _document().to_dict()
    data["format_version"] = 6
    with pytest.raises(ValueError, match="format_version 6"):
        PatternDocument.from_dict(data)
    data["format_version"] = 5
    assert PatternDocument.from_dict(data) == _document()
