"""Tests for the browser app's state layer (runs in plain CPython)."""

from __future__ import annotations

import functools
from pathlib import Path

import pytest

from kvale.core import Editor, Mark, PatternDocument, build_colour_grid
from kvale.core.serialization import load_document
from kvale.core.symmetry import expand_marks
from kvale.core.editing import CORNERS, EDGES, get_end_piece
from kvale_web.state import (
    DOCUMENT,
    EDIT_TARGETS,
    HISTORY_LIMIT,
    STATUS,
    TARGET_LABEL_KEYS,
    VIEW,
    AppState,
)

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "flower-band.json"


def recorder(state: AppState, *topics: str) -> list[str]:
    seen: list[str] = []
    state.subscribe(seen.append, *topics)
    return seen


def test_edit_notifies_document_listeners_only_on_change() -> None:
    state = AppState()
    seen = recorder(state, DOCUMENT)
    state.edit(lambda editor: editor.paint(1, 1, 0))
    state.edit(lambda editor: editor.paint(1, 1, 0))  # same again: no change
    assert seen == [DOCUMENT]
    assert state.editor.can_undo


def test_topic_filter_and_unsubscribe() -> None:
    state = AppState()
    view = recorder(state, VIEW)
    every: list[str] = []
    unsubscribe = state.subscribe(every.append)
    state.select_slot(2)
    state.edit(lambda editor: editor.paint(0, 0, 2))
    unsubscribe()
    state.set_mode("preview")
    assert view == [VIEW, VIEW]
    assert every == [VIEW, DOCUMENT]


def test_unknown_topic_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown topics"):
        AppState().subscribe(lambda _topic: None, "colour")


def test_stroke_is_one_undo_step_and_notifies_each_edit() -> None:
    state = AppState()
    seen = recorder(state, DOCUMENT)
    state.begin_stroke()
    for y in range(3):
        state.edit(functools.partial(Editor.paint, x=0, y=y, colour_slot=0))
    assert not state.editor.can_undo  # recorded when the stroke ends
    state.end_stroke()
    assert seen == [DOCUMENT] * 4
    assert state.undo()
    assert state.document.motif == []
    assert not state.editor.can_undo


def test_undo_closes_an_open_stroke() -> None:
    state = AppState()
    state.begin_stroke()
    state.edit(lambda editor: editor.paint(0, 0, 0))
    assert state.undo()
    assert state.document.motif == []
    assert state.redo()
    assert len(state.document.motif) == 1


def test_undo_clamps_active_slot() -> None:
    state = AppState()
    state.edit(lambda editor: editor.add_colour("#123456"))
    state.select_slot(4)
    seen = recorder(state, VIEW)
    state.undo()
    assert state.active_slot == 3
    assert seen == [VIEW]


def test_select_slot_leaves_unpick_and_ignores_bad_index() -> None:
    state = AppState()
    state.set_tool("unpick")
    state.select_slot(99)
    assert state.erase_tool
    state.select_slot(1)
    assert (state.active_slot, state.tool, state.erase_tool) == (1, "cross", False)


def test_select_slot_keeps_backstitch() -> None:
    state = AppState()
    state.set_tool("back")
    state.select_slot(2)
    assert (state.active_slot, state.tool) == (2, "back")


def test_tool_changes_notify_view_and_close_the_stroke() -> None:
    state = AppState()
    assert state.tool == "cross"
    seen = recorder(state, VIEW)
    state.begin_stroke()
    state.paint_cell(0, 0)
    state.set_tool("unpick")
    state.set_tool("unpick")  # unchanged: no notification
    assert seen == [VIEW]
    assert state.editor.can_undo  # the stroke was closed
    state.erase_cell(0, 0)
    assert state.document.motif == []
    with pytest.raises(ValueError, match="Unknown tool"):
        state.set_tool("needle")  # type: ignore[arg-type]


def test_mode_is_checked() -> None:
    state = AppState()
    state.set_mode("preview")
    assert state.mode == "preview"
    with pytest.raises(ValueError, match="Unknown mode"):
        state.set_mode("print")  # type: ignore[arg-type]


def test_edit_targets_cover_core_end_pieces_and_have_labels() -> None:
    assert EDIT_TARGETS == ("unit", *EDGES, *CORNERS)
    assert set(TARGET_LABEL_KEYS) == set(EDIT_TARGETS)


def test_set_edit_target_switches_to_edit_mode() -> None:
    state = AppState()
    state.set_mode("preview")
    seen = recorder(state, VIEW)
    state.set_edit_target("top_right")
    assert (state.edit_target, state.mode) == ("top_right", "edit")
    state.set_edit_target("top_right")  # unchanged: no notification
    assert seen == [VIEW]
    with pytest.raises(ValueError, match="Unknown edit target"):
        state.set_edit_target("middle")  # type: ignore[arg-type]


def test_paint_and_erase_follow_the_edit_target() -> None:
    state = AppState()
    state.edit(lambda editor: editor.set_symmetry(["mirror_x"]))
    state.set_edit_target("right")
    # Outside the minimal cell of the unit, but inside the right end piece.
    assert state.paint_cell(10, 1).changed
    assert state.document.motif == []  # the unit is untouched
    piece = get_end_piece(state.document, "right")
    assert piece is not None and [(m.x, m.y) for m in piece.added_marks] == [(10, 1)]
    assert state.erase_cell(10, 1).changed
    assert not state.paint_cell(99, 99).changed  # outside the end piece

    state.set_edit_target("unit")
    assert not state.paint_cell(10, 1).changed  # back to the minimal cell


def test_load_returns_to_the_unit() -> None:
    state = AppState()
    state.set_edit_target("bottom_left")
    seen = recorder(state, VIEW, DOCUMENT)
    state.load(PatternDocument())
    assert state.edit_target == "unit"
    assert seen == [VIEW, DOCUMENT]


def test_removed_symmetry_sets_status() -> None:
    state = AppState()
    state.edit(lambda editor: editor.set_symmetry(["rotate_90"]))
    seen = recorder(state, STATUS)
    state.edit(lambda editor: editor.set_grid(unit_width=5))
    assert seen == [STATUS]
    assert state.status == ("symmetry.switchedOff", {})


def test_load_resets_history() -> None:
    state = AppState()
    state.edit(lambda editor: editor.paint(0, 0, 0))
    state.load(PatternDocument(unit_width=3, unit_height=3))
    assert not state.editor.can_undo
    assert state.document.unit_width == 3


def test_history_is_capped() -> None:
    state = AppState()
    assert state.editor.history_limit == HISTORY_LIMIT == 100
    for x in range(HISTORY_LIMIT + 5):
        state.edit(functools.partial(Editor.paint, x=x % 12, y=x // 12, colour_slot=0))
    undone = 0
    while state.undo():
        undone += 1
    assert undone == HISTORY_LIMIT


def test_load_example_then_edit_and_undo() -> None:
    document = load_document(EXAMPLE)
    state = AppState()
    seen = recorder(state, DOCUMENT)
    state.load(document)
    assert seen == [DOCUMENT]
    assert (state.document.unit_width, state.document.unit_height) == (12, 12)
    grid = build_colour_grid(state.document)
    assert len(grid) == 12 * 2 and len(grid[0]) == 12 * 7
    before = state.document.to_dict()
    state.edit(lambda editor: editor.erase(*_first_seed(state)))
    assert state.document.to_dict() != before
    assert state.undo()
    assert state.document.to_dict() == before


def _first_seed(state: AppState) -> tuple[int, int]:
    mark = state.document.motif[0]
    return mark.x, mark.y


def _expanded(state: AppState) -> set[tuple[int, int]]:
    doc = state.document
    return {
        (mark.x, mark.y)
        for mark in expand_marks(doc.motif, doc.unit_width, doc.unit_height, doc.symmetry)
    }


def test_click_outside_minimal_cell_does_nothing() -> None:
    state = AppState()
    state.edit(lambda editor: editor.set_symmetry(["mirror_x"]))
    seen = recorder(state, DOCUMENT)
    assert not state.paint_cell(10, 1).changed  # right half: a mirror copy
    assert state.document.motif == []
    assert seen == []

    assert state.paint_cell(1, 1).changed
    assert _expanded(state) == {(1, 1), (10, 1)}  # mirrored automatically
    assert not state.erase_cell(10, 1).changed  # erasing the copy does nothing too
    assert _expanded(state) == {(1, 1), (10, 1)}
    assert state.erase_cell(1, 1).changed
    assert state.document.motif == []
    assert seen == [DOCUMENT, DOCUMENT]


def test_minimal_cell_follows_symmetry_and_unit_size() -> None:
    state = AppState()
    assert len(state.editable_cells) == 12 * 12  # identity: the whole unit
    state.edit(lambda editor: editor.set_symmetry(["mirror_x", "mirror_y"]))
    assert state.editable_cells == {(x, y) for x in range(6) for y in range(6)}
    state.edit(lambda editor: editor.set_grid(unit_width=7))
    assert state.editable_cells == {(x, y) for x in range(4) for y in range(6)}
    state.undo()
    state.undo()
    assert len(state.editable_cells) == 12 * 12


def test_marks_outside_minimal_cell_are_kept() -> None:
    # A file made before the restriction may have marks outside the minimal cell.
    state = AppState()
    state.edit(lambda editor: editor.paint(10, 1, 0))
    state.edit(lambda editor: editor.set_symmetry(["mirror_x"]))
    assert (10, 1) not in state.editable_cells
    assert state.document.motif == [Mark(10, 1, 0)]
    assert _expanded(state) == {(1, 1), (10, 1)}
    assert not state.erase_cell(10, 1).changed
    assert not state.paint_cell(1, 1).changed  # the copy already has this colour
