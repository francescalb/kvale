"""Thread brands, thread references and how documents store them."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kvale.core import Editor, PatternDocument
from kvale.core.serialization import load_document
from kvale.core.threads import (
    BRANDS,
    FAMILIES,
    brand_name,
    brand_threads,
    colour_family,
    display_code,
    find_thread,
    infer_thread,
    parse_thread_ref,
    search_threads,
    slot_threads,
)

ROOT = Path(__file__).resolve().parent.parent


def test_brands_are_data_and_only_dmc_has_threads() -> None:
    assert [brand.name for brand in BRANDS] == ["DMC", "Anchor", "Madeira"]
    assert [brand.available for brand in BRANDS] == [True, False, False]
    assert len(brand_threads("dmc")) == 454
    assert brand_threads("anchor") == ()
    assert brand_threads("nope") == ()
    assert brand_name("dmc") == "DMC"
    assert brand_name("future") == "FUTURE"


def test_references() -> None:
    assert parse_thread_ref("dmc:321") == ("dmc", "321")
    assert parse_thread_ref("321") is None
    assert parse_thread_ref(":321") is None
    assert display_code("dmc:B5200") == ("DMC", "B5200")
    thread = find_thread("dmc:321")
    assert thread is not None
    assert thread.name == "Red"
    assert thread.ref == "dmc:321"
    assert find_thread("dmc:ecru") == find_thread("dmc:Ecru")
    assert find_thread("dmc:99999") is None
    assert find_thread(None) is None
    assert infer_thread(thread.hex_colour.upper()) == "dmc:321"
    assert infer_thread("#123457") is None


def test_search_ignores_the_brand_name_and_filters_by_family() -> None:
    assert [t.code for t in search_threads("dmc", "321")] == [t.code for t in search_threads("dmc", "DMC 321")]
    assert "321" in [t.code for t in search_threads("dmc", "dmc-321")]
    assert search_threads("dmc", "") == brand_threads("dmc")
    assert search_threads("dmc", "no such thread") == ()
    reds = search_threads("dmc", family="red")
    assert reds and all(colour_family(t.hex_colour) == "red" for t in reds)
    every = sum(len(search_threads("dmc", family=f)) for f in FAMILIES if f != "all")
    assert every == len(brand_threads("dmc"))


@pytest.mark.parametrize(
    ("colour", "family"),
    [("#ffffff", "neutral"), ("#000000", "neutral"), ("#808080", "neutral"), ("#cc1020", "red"),
     ("#ffb0c0", "pink"), ("#ff8b00", "orange"), ("#ffd800", "yellow"), ("#20a040", "green"),
     ("#2040c0", "blue"), ("#7030a0", "purple"), ("#6b3d1e", "brown")],
)
def test_colour_family(colour: str, family: str) -> None:
    assert colour_family(colour) == family


def test_old_files_read_dmc_colours_as_dmc_and_others_as_own() -> None:
    red = find_thread("dmc:321")
    assert red is not None
    document = PatternDocument(palette_sequences=[[red.hex_colour, "#123457"], ["#b1172b"]])
    assert slot_threads(document) == [["dmc:321", None], [None]]
    assert "palette_threads" not in document.to_dict()


def test_editor_stores_references_and_keeps_old_documents_unchanged() -> None:
    editor = Editor(PatternDocument())
    editor.set_colour_sequence(0, ["#123456"])  # no references given: stays an old-style document
    assert editor.document.palette_threads is None

    red = find_thread("dmc:321")
    assert red is not None
    editor.add_colour(red.hex_colour, ["dmc:321"])
    assert editor.document.palette_threads == [[None], [None], [None], [None], ["dmc:321"]]
    # An own colour that happens to be a DMC screen colour stays an own colour.
    editor.set_colour_sequence(1, [red.hex_colour, "#000000"], [None, None])
    assert slot_threads(editor.document)[1] == [None, None]
    # Without references the colours decide.
    editor.set_colour_sequence(2, [red.hex_colour])
    assert slot_threads(editor.document)[2] == ["dmc:321"]
    with pytest.raises(ValueError, match="every colour"):
        editor.set_colour_sequence(3, ["#000000"], [])
    editor.undo()
    assert slot_threads(editor.document)[2] == [None]


def test_references_round_trip_and_old_readers_still_get_colours(tmp_path: Path) -> None:
    editor = Editor(PatternDocument())
    editor.add_colour("#c72b3b", ["dmc:321"])
    data = editor.document.to_dict()
    assert data["format_version"] == 4  # an optional field: no new format version
    assert data["palette_threads"][-1] == ["dmc:321"]
    assert data["palette_sequences"][-1] == ["#c72b3b"]
    path = tmp_path / "pattern.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert load_document(path) == editor.document


def test_bad_references_are_rejected() -> None:
    data = PatternDocument().to_dict()
    data["palette_threads"] = [["dmc:321"]]
    with pytest.raises(ValueError, match="one entry per palette colour"):
        PatternDocument.from_dict(data)
    data["palette_threads"] = "dmc:321"
    with pytest.raises(ValueError, match="list of lists"):
        PatternDocument.from_dict(data)


def test_example_file_is_unchanged_by_loading() -> None:
    document = load_document(ROOT / "examples" / "flower-band.json")
    assert document.palette_threads is None
    assert len(slot_threads(document)) == len(document.palette_sequences)
