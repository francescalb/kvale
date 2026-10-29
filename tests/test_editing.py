import pytest

from kvale.core.editing import (
    add_palette_colour,
    erase_cell,
    find_source_mark,
    insert_column,
    insert_row,
    paint_cell,
    remove_column,
    remove_row,
    resize_sequence,
    resize_unit,
    set_palette_sequence,
    set_repeats,
    set_symmetry,
)
from kvale.core.model import Mark, PatternDocument
from kvale.core.symmetry import normalise_symmetry


def _positions(document: PatternDocument) -> set[tuple[int, int, int]]:
    return {(mark.x, mark.y, mark.colour_slot) for mark in document.motif}


def test_insert_column_shifts_marks_at_and_after_index() -> None:
    document = PatternDocument(unit_width=4, unit_height=3, motif=[Mark(0, 0, 0), Mark(2, 1, 1)])

    insert_column(document, 2)

    assert document.unit_width == 5
    assert _positions(document) == {(0, 0, 0), (3, 1, 1)}


def test_insert_column_index_is_clamped() -> None:
    document = PatternDocument(unit_width=3, unit_height=3, motif=[Mark(0, 0, 0)])

    insert_column(document, -5)
    assert _positions(document) == {(1, 0, 0)}

    insert_column(document, 99)
    assert document.unit_width == 5
    assert _positions(document) == {(1, 0, 0)}


def test_remove_column_drops_its_marks_and_shifts_later_ones() -> None:
    document = PatternDocument(
        unit_width=4, unit_height=2, motif=[Mark(0, 0, 0), Mark(1, 0, 1), Mark(3, 1, 2)]
    )

    remove_column(document, 1)

    assert document.unit_width == 3
    assert _positions(document) == {(0, 0, 0), (2, 1, 2)}


def test_remove_column_keeps_last_column() -> None:
    document = PatternDocument(unit_width=1, unit_height=2, motif=[Mark(0, 0, 0)])

    assert remove_column(document, 0) == []
    assert document.unit_width == 1
    assert _positions(document) == {(0, 0, 0)}


def test_remove_column_index_is_clamped_to_last_column() -> None:
    document = PatternDocument(unit_width=3, unit_height=1, motif=[Mark(2, 0, 0), Mark(1, 0, 1)])

    remove_column(document, 10)

    assert document.unit_width == 2
    assert _positions(document) == {(1, 0, 1)}


def test_insert_and_remove_row() -> None:
    document = PatternDocument(unit_width=2, unit_height=3, motif=[Mark(0, 0, 0), Mark(1, 2, 1)])

    insert_row(document, 1)
    assert document.unit_height == 4
    assert _positions(document) == {(0, 0, 0), (1, 3, 1)}

    remove_row(document, 0)
    assert document.unit_height == 3
    assert _positions(document) == {(1, 2, 1)}


def test_remove_row_keeps_last_row() -> None:
    document = PatternDocument(unit_width=2, unit_height=1, motif=[Mark(1, 0, 0)])

    remove_row(document, 0)

    assert document.unit_height == 1
    assert _positions(document) == {(1, 0, 0)}


def test_column_change_keeps_square_unit_with_quarter_turn_symmetry() -> None:
    # The symmetry ties column 0 to the last column and, through the quarter
    # turn, to the first and last rows, so all four are inserted.
    document = PatternDocument(
        unit_width=4, unit_height=4, symmetry=["identity", "mirror_x", "rotate_90", "diag_main"]
    )

    removed = insert_column(document, 0)

    assert removed == []
    assert (document.unit_width, document.unit_height) == (6, 6)
    assert document.symmetry == ["identity", "mirror_x", "rotate_90", "diag_main"]


def test_resize_unit_crops_marks_and_clamps_size() -> None:
    document = PatternDocument(
        unit_width=6, unit_height=6, motif=[Mark(0, 0, 0), Mark(4, 1, 1), Mark(1, 4, 2)]
    )

    resize_unit(document, 3, 5)
    assert (document.unit_width, document.unit_height) == (3, 5)
    assert _positions(document) == {(0, 0, 0), (1, 4, 2)}

    resize_unit(document, 0, -2)
    assert (document.unit_width, document.unit_height) == (1, 1)
    assert _positions(document) == {(0, 0, 0)}


def test_resize_unit_applies_symmetry_rules() -> None:
    document = PatternDocument(unit_width=4, unit_height=4, symmetry=["identity", "rotate_270"])

    assert resize_unit(document, 4, 5) == ["rotate_270"]
    assert document.symmetry == ["identity"]


def test_set_repeats_clamps_to_one() -> None:
    document = PatternDocument()

    set_repeats(document, 0, 3)

    assert (document.repeats_x, document.repeats_y) == (1, 3)


def test_normalise_symmetry_always_includes_identity() -> None:
    assert normalise_symmetry([], 4, 4) == (["identity"], [])
    assert normalise_symmetry(["mirror_y"], 3, 5) == (["identity", "mirror_y"], [])


def test_normalise_symmetry_uses_canonical_order_and_drops_unknown() -> None:
    allowed, removed = normalise_symmetry(["diag_anti", "mirror_x", "spin", "identity"], 4, 4)

    assert allowed == ["identity", "mirror_x", "diag_anti"]
    assert removed == []


def test_normalise_symmetry_removes_square_only_on_non_square_unit() -> None:
    selected = ["identity", "mirror_x", "mirror_y", "rotate_180", "rotate_90", "rotate_270",
                "diag_main", "diag_anti"]

    allowed, removed = normalise_symmetry(selected, 6, 4)

    assert allowed == ["identity", "mirror_x", "mirror_y", "rotate_180"]
    assert removed == ["rotate_90", "rotate_270", "diag_main", "diag_anti"]


def test_set_symmetry_reports_removed_operations() -> None:
    document = PatternDocument(unit_width=6, unit_height=4)

    removed = set_symmetry(document, ["mirror_x", "diag_main"])

    assert removed == ["diag_main"]
    assert document.symmetry == ["identity", "mirror_x"]


def test_find_source_mark_for_generated_copy() -> None:
    source = Mark(1, 1, 2)
    document = PatternDocument(
        unit_width=6, unit_height=6, symmetry=["identity", "mirror_x"], motif=[source]
    )

    assert find_source_mark(document, 1, 1) == source
    assert find_source_mark(document, 4, 1) == source
    assert find_source_mark(document, 4, 4) is None


def test_find_source_mark_prefers_first_mark_in_motif() -> None:
    first = Mark(4, 0, 1)
    second = Mark(1, 0, 0)
    document = PatternDocument(
        unit_width=6, unit_height=1, symmetry=["identity", "mirror_x"], motif=[first, second]
    )

    assert find_source_mark(document, 1, 0) == first


def test_paint_generated_copy_recolours_source_mark() -> None:
    document = PatternDocument(
        unit_width=6, unit_height=6, symmetry=["identity", "mirror_x"], motif=[Mark(1, 1, 0)]
    )

    assert paint_cell(document, 4, 1, 3)

    assert document.motif == [Mark(1, 1, 3)]


def test_paint_empty_cell_adds_mark() -> None:
    document = PatternDocument(unit_width=3, unit_height=3)

    assert paint_cell(document, 2, 1, 1)
    assert document.motif == [Mark(2, 1, 1)]


def test_paint_outside_unit_does_nothing() -> None:
    document = PatternDocument(unit_width=3, unit_height=3)

    assert not paint_cell(document, 3, 0, 1)
    assert not paint_cell(document, 0, -1, 1)
    assert document.motif == []


def test_erase_generated_copy_removes_source_mark() -> None:
    document = PatternDocument(
        unit_width=6, unit_height=6, symmetry=["identity", "mirror_y"], motif=[Mark(2, 0, 0)]
    )

    assert erase_cell(document, 2, 5)
    assert document.motif == []
    assert not erase_cell(document, 2, 5)
    assert not erase_cell(document, 99, 0)


def test_add_palette_colour_appends_one_colour_sequence() -> None:
    document = PatternDocument(palette_sequences=[["#000000"]])

    assert add_palette_colour(document, "#abcdef") == 1
    assert document.palette_sequences == [["#000000"], ["#abcdef"]]
    assert document.palette == ["#000000", "#abcdef"]


def test_set_palette_sequence_updates_base_colour() -> None:
    document = PatternDocument(palette_sequences=[["#000000"], ["#111111"]])
    sequence = ["#ff0000", "#00ff00"]

    set_palette_sequence(document, 1, sequence)
    sequence.append("#0000ff")

    assert document.palette_sequences == [["#000000"], ["#ff0000", "#00ff00"]]
    assert document.palette == ["#000000", "#ff0000"]


def test_set_palette_sequence_rejects_bad_input() -> None:
    document = PatternDocument(palette_sequences=[["#000000"]])

    with pytest.raises(ValueError, match="at least one colour"):
        set_palette_sequence(document, 0, [])
    with pytest.raises(IndexError):
        set_palette_sequence(document, 1, ["#ffffff"])
    assert document.palette_sequences == [["#000000"]]


def test_resize_sequence_extends_with_last_colour_and_truncates() -> None:
    assert resize_sequence(["#a", "#b"], 4) == ["#a", "#b", "#b", "#b"]
    assert resize_sequence(["#a", "#b", "#c"], 1) == ["#a"]
    assert resize_sequence(["#a"], 0) == ["#a"]
    with pytest.raises(ValueError):
        resize_sequence([], 2)
