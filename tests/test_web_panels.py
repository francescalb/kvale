"""The side panels' logic without the DOM (kvale_web.panels.*_model), in plain CPython."""

from __future__ import annotations

import pytest

from kvale.core import Backstitch, Editor, Mark, PatternDocument
from kvale.core.threads import Thread, find_thread
from kvale_web.panels.colour_model import (
    QUICK_THREADS,
    ColourDraft,
    PickerState,
    band_preview,
    colour_info,
    parse_colour,
    slot_colours,
    text_colour_on,
    thread_rows,
)
from kvale_web.panels.grid_model import (
    SYMMETRY_GROUPS,
    clamp_setting,
    edge_diagram,
    square_size,
    symmetry_icon,
    toggled_symmetry,
)
from kvale_web.panels.lines_model import LinesChoice, lines_effect



def _thread(ref: str) -> Thread:
    thread = find_thread(ref)
    assert thread is not None
    return thread


RED = _thread("dmc:321")


def test_colour_info_names_the_brand() -> None:
    info = colour_info(RED.hex_colour, "dmc:321")
    assert info.code == ("DMC", "321") and info.name == "Red" and info.is_thread
    own = colour_info("#123456", None)
    assert own.code is None and not own.is_thread
    unknown_brand = colour_info("#123456", "anchor:46")
    assert unknown_brand.code == ("Anchor", "46") and unknown_brand.name == ""
    assert all(find_thread(ref) for ref in QUICK_THREADS)


def test_slot_colours_and_thread_rows() -> None:
    document = PatternDocument(
        palette_sequences=[[RED.hex_colour, "#000000"], ["#123456"], [RED.hex_colour]],
        motif=[Mark(0, 0, 0), Mark(1, 0, 2)],
    )
    assert [[i.code for i in s] for s in slot_colours(document)] == [
        [("DMC", "321"), ("DMC", "310")], [None], [("DMC", "321")]
    ]
    # Slot 2 is not stitched, slot 3 repeats slot 1's thread; sequences off: first colours only.
    assert [row.ref for row in thread_rows(document)] == ["dmc:321"]
    document.use_palette_sequence = True
    assert [row.ref for row in thread_rows(document)] == ["dmc:321", "dmc:310"]
    document.backstitches = [Backstitch(0, 0, 1, 1, 1)]
    assert [row.hex_colour for row in thread_rows(document)][-1] == "#123456"
    assert thread_rows(PatternDocument()) == []


@pytest.mark.parametrize(
    ("text", "colour"),
    [("#C72B3B", "#c72b3b"), ("c72b3b", "#c72b3b"), ("#c23", "#cc2233"), ("199, 43, 59", "#c72b3b"),
     ("rgb(199 43 59)", "#c72b3b"), ("256,0,0", None), ("red", None), ("", None)],
)
def test_parse_colour(text: str, colour: str | None) -> None:
    assert parse_colour(text) == colour


def test_text_colour_and_band_preview() -> None:
    assert text_colour_on("#ffffff") != text_colour_on("#000000")
    assert band_preview(["#a", "#b"], 5, True) == ["#a", "#b", "#a", "#b", "#a"]
    assert band_preview(["#a", "#b"], 50, False) == ["#a"] * 10
    assert band_preview(["#a"], 0, True) == ["#a"]


def test_colour_draft_resizes_1_to_24_and_keeps_threads() -> None:
    editor = Editor(PatternDocument())
    draft = ColourDraft.from_document(editor.document, 0)
    draft.set_colour(RED.hex_colour, "dmc:321")
    draft.resize(3)
    assert draft.refs == ["dmc:321"] * 3
    draft.select(2)
    draft.set_colour("#ABCDEF", None)
    assert draft.colours[2] == "#abcdef" and draft.current.code is None
    draft.resize(100)
    assert len(draft.colours) == 24
    draft.resize(0)
    assert draft.colours == [RED.hex_colour] and draft.part == 0
    draft.select(5)  # out of range: ignored
    assert draft.part == 0
    editor.set_colour_sequence(0, draft.colours, draft.refs)
    assert editor.document.palette_threads is not None
    assert editor.document.palette_threads[0] == ["dmc:321"]


def test_picker_state() -> None:
    picker = PickerState()
    picker.reset("dmc:321")
    assert picker.selected == "dmc:321" and picker.chosen == RED
    assert len(picker.results) == 454
    picker.set_query("DMC 321")
    assert "321" in [t.code for t in picker.results]
    picker.set_family("blue")
    assert all(t.code != "321" for t in picker.results)
    assert not picker.set_brand("anchor")  # coming later
    assert picker.brand == "dmc"
    picker.reset("anchor:46")
    assert picker.brand == "dmc" and picker.selected is None and picker.query == ""


def test_lines_effect_with_and_without_symmetry() -> None:
    document = PatternDocument(unit_width=12, unit_height=10)
    add_bottom = lines_effect(document, LinesChoice())
    assert add_bottom.rows == (10,) and add_bottom.columns == ()
    assert add_bottom.labels() == [("grid.newRowN", 11)]
    assert (add_bottom.new_width, add_bottom.new_height) == (12, 11)

    document.symmetry = ["identity", "mirror_x"]
    remove_first = lines_effect(document, LinesChoice(insertion=False, place="first_column"))
    assert remove_first.columns == (0, 11) and remove_first.count == 2
    assert remove_first.labels() == [("grid.colN", 1), ("grid.colN", 12)]
    assert remove_first.allowed and remove_first.new_width == 10
    add_first = lines_effect(document, LinesChoice(insertion=True, place="first_column"))
    assert add_first.labels() == [("grid.newColN", 1), ("grid.newColN", 14)]

    numbered = LinesChoice(insertion=False, place="row", number=99)
    assert lines_effect(document, numbered).rows == (9,)
    assert numbered.number == 10  # clamped to the last row

    one_row = PatternDocument(unit_width=3, unit_height=1)
    assert not lines_effect(one_row, LinesChoice(insertion=False, place="top_row")).allowed
    assert lines_effect(one_row, LinesChoice(insertion=True, place="top_row")).allowed


@pytest.mark.parametrize(
    ("value", "expected"), [("12", 12), ("0", 1), ("150", 100), ("7,6", 8), ("", None), ("x", None), ("nan", None)]
)
def test_clamp_setting(value: str, expected: int | None) -> None:
    assert clamp_setting(value) == expected


def test_symmetry_tiles() -> None:
    assert SYMMETRY_GROUPS[0] == ("identity", "mirror_x", "mirror_y", "rotate_180")
    assert set(SYMMETRY_GROUPS[1]) == {"rotate_90", "rotate_270", "diag_main", "diag_anti"}
    assert toggled_symmetry(["identity"], "identity") == ["identity"]
    assert toggled_symmetry(["identity", "rotate_90"], "mirror_x") == ["identity", "mirror_x", "rotate_90"]
    assert toggled_symmetry(["identity", "mirror_x"], "mirror_x") == ["identity"]
    assert square_size(PatternDocument(unit_width=9, unit_height=14)) == 14
    for operation in (*SYMMETRY_GROUPS[0], *SYMMETRY_GROUPS[1]):
        svg = symmetry_icon(operation)
        assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert symmetry_icon("identity").count("<rect") == 4  # frame + three seed stitches
    assert "stroke-dasharray" in symmetry_icon("mirror_x")


def test_edge_diagram_follows_the_toggles() -> None:
    every = edge_diagram(PatternDocument())
    assert (every.width, every.height) == (15, 8)
    assert len(every.units) == 6
    shared = edge_diagram(PatternDocument(repeat_left_column=False, repeat_top_row=False))
    assert (shared.width, shared.height) == (13, 7)
    kinds = {cell.kind for cell in shared.cells}
    assert kinds == {"column", "row", "inner"}
