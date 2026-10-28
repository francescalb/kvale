"""Tests for the browser app's state layer (runs in plain CPython)."""

from __future__ import annotations

import functools

import pytest

from kvale.core import Editor, PatternDocument
from kvale_web.state import DOCUMENT, STATUS, VIEW, AppState


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


def test_select_slot_turns_off_eraser_and_ignores_bad_index() -> None:
    state = AppState()
    state.set_erase_tool(True)
    state.select_slot(99)
    assert state.erase_tool
    state.select_slot(1)
    assert (state.active_slot, state.erase_tool) == (1, False)


def test_removed_symmetry_sets_status() -> None:
    state = AppState()
    state.edit(lambda editor: editor.set_symmetry(["rotate_90"]))
    seen = recorder(state, STATUS)
    state.edit(lambda editor: editor.set_grid(unit_width=5))
    assert seen == [STATUS]
    assert state.status == ("symmetry_removed", {"operations": ("rotate_90",)})


def test_load_resets_history() -> None:
    state = AppState()
    state.edit(lambda editor: editor.paint(0, 0, 0))
    state.load(PatternDocument(unit_width=3, unit_height=3))
    assert not state.editor.can_undo
    assert state.document.unit_width == 3
