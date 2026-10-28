import pytest

from kvale.core.editor import Editor
from kvale.core.model import Mark, PatternDocument


def _editor() -> Editor:
    return Editor(PatternDocument(unit_width=4, unit_height=4))


def test_new_editor_has_default_document_and_no_history() -> None:
    editor = Editor()

    assert editor.document == PatternDocument()
    assert not editor.can_undo
    assert not editor.can_redo
    assert not editor.undo()
    assert not editor.redo()


def test_undo_and_redo_paint() -> None:
    editor = _editor()

    result = editor.paint(1, 2, 0)

    assert result.changed
    assert editor.document.motif == [Mark(1, 2, 0)]
    assert editor.undo()
    assert editor.document.motif == []
    assert editor.can_redo
    assert editor.redo()
    assert editor.document.motif == [Mark(1, 2, 0)]


def test_unchanged_edit_does_not_create_undo_step() -> None:
    editor = _editor()

    assert not editor.erase(0, 0).changed
    assert not editor.paint(10, 10, 0).changed
    assert not editor.set_symmetry(["identity"]).changed
    editor.load(PatternDocument(unit_width=1, unit_height=1))
    assert not editor.remove_column(0).changed
    assert not editor.can_undo


def test_new_edit_clears_redo() -> None:
    editor = _editor()
    editor.paint(0, 0, 0)
    editor.undo()

    editor.paint(1, 1, 1)

    assert not editor.can_redo


def test_batch_groups_stroke_into_one_undo_step() -> None:
    editor = _editor()
    editor.paint(3, 3, 1)

    editor.begin_batch()
    for x in range(3):
        assert editor.paint(x, 0, 0).changed
    assert editor.end_batch()

    assert len(editor.document.motif) == 4
    assert editor.undo()
    assert editor.document.motif == [Mark(3, 3, 1)]
    assert editor.undo()
    assert editor.document.motif == []


def test_nested_and_empty_batches() -> None:
    editor = _editor()

    with editor.batch():
        with editor.batch():
            editor.paint(0, 0, 0)
        editor.paint(1, 0, 0)
    assert editor.undo()
    assert editor.document.motif == []
    assert not editor.can_undo

    with editor.batch():
        editor.erase(0, 0)
    assert not editor.can_undo


def test_batch_misuse_raises() -> None:
    editor = _editor()
    with pytest.raises(RuntimeError):
        editor.end_batch()

    editor.paint(0, 0, 0)
    editor.begin_batch()
    with pytest.raises(RuntimeError):
        editor.undo()
    with pytest.raises(RuntimeError):
        editor.load(PatternDocument())
    editor.end_batch()


def test_undo_restores_snapshot_not_shared_state() -> None:
    editor = _editor()
    editor.add_colour("#123456")
    editor.set_colour_sequence(4, ["#000000", "#ffffff"])

    assert editor.undo()
    assert editor.document.palette_sequences[4] == ["#123456"]
    assert editor.undo()
    assert len(editor.document.palette_sequences) == 4


def test_history_limit_drops_oldest_steps() -> None:
    editor = Editor(PatternDocument(unit_width=4, unit_height=4), history_limit=2)
    for x in range(4):
        editor.paint(x, 0, 0)

    assert editor.undo()
    assert editor.undo()
    assert not editor.undo()
    assert len(editor.document.motif) == 2


def test_load_replaces_document_and_clears_history() -> None:
    editor = _editor()
    editor.paint(0, 0, 0)
    replacement = PatternDocument(unit_width=2, unit_height=2)

    editor.load(replacement)

    assert editor.document is replacement
    assert not editor.can_undo


def test_insert_column_reports_removed_symmetry_and_undo_restores_it() -> None:
    editor = _editor()
    editor.set_symmetry(["identity", "rotate_90"])

    result = editor.insert_column(1)

    assert result.changed
    assert result.removed_symmetry == ("rotate_90",)
    assert editor.document.symmetry == ["identity"]
    editor.undo()
    assert editor.document.symmetry == ["identity", "rotate_90"]
    assert editor.document.unit_width == 4


def test_set_symmetry_on_non_square_unit() -> None:
    editor = Editor(PatternDocument(unit_width=6, unit_height=4))

    result = editor.set_symmetry(["mirror_x", "diag_anti"])

    assert result.removed_symmetry == ("diag_anti",)
    assert editor.document.symmetry == ["identity", "mirror_x"]


def test_set_grid_is_one_step_and_crops_marks() -> None:
    editor = Editor(PatternDocument(unit_width=6, unit_height=6, motif=[Mark(5, 5, 0), Mark(0, 0, 1)]))

    result = editor.set_grid(
        unit_width=4,
        unit_height=4,
        repeats_x=0,
        repeats_y=7,
        repeat_left_column=False,
        repeat_bottom_row=False,
    )

    document = editor.document
    assert result.changed
    assert (document.unit_width, document.unit_height) == (4, 4)
    assert (document.repeats_x, document.repeats_y) == (1, 7)
    assert not document.repeat_left_column
    assert document.repeat_right_column
    assert not document.repeat_bottom_row
    assert document.motif == [Mark(0, 0, 1)]
    editor.undo()
    assert editor.document.motif == [Mark(5, 5, 0), Mark(0, 0, 1)]
    assert not editor.can_undo


def test_set_grid_without_arguments_keeps_settings() -> None:
    editor = _editor()

    assert not editor.set_grid().changed


def test_colour_settings() -> None:
    editor = _editor()

    assert editor.set_use_palette_sequence(True).changed
    assert editor.set_background("#000000").changed
    assert not editor.set_background("#000000").changed

    assert editor.document.use_palette_sequence
    assert editor.document.background == "#000000"
    editor.undo()
    assert editor.document.background == "#ffffff"
