"""Tests for the browser-free file logic of the web app (``kvale_web.files.logic``)."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from PIL import Image

from kvale.core import Mark, PatternDocument, RepeatOverride, build_colour_grid
from kvale.core.serialization import load_document
from kvale_web.files.logic import (
    DocSession,
    OpenError,
    UrlSource,
    autosave_payload,
    decode_data_hash,
    encode_data_hash,
    file_name,
    fingerprint,
    parse_document,
    png_cell_size,
    read_autosave,
    render_png,
    serialize,
    stem_of,
    url_source,
)

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "flower-band.json"


# Reading and writing ---------------------------------------------------


def test_serialize_round_trips_the_example() -> None:
    document = load_document(EXAMPLE)
    again = parse_document(serialize(document))
    assert again == document
    assert json.loads(serialize(document)) == document.to_dict()


@pytest.mark.parametrize("version", [None, 1, 2, 3, 4, 5])
def test_opens_every_format_version_the_core_reads(version: int | None) -> None:
    data = PatternDocument(motif=[Mark(1, 2, 0)]).to_dict()
    if version is None:
        del data["format_version"]
    else:
        data["format_version"] = version
    document = parse_document(json.dumps(data))
    assert document.motif == [Mark(1, 2, 0)]


def test_opens_a_corner_file() -> None:
    document = PatternDocument(top_left_repeat_override=RepeatOverride(added_marks=[Mark(0, 0, 1)]))
    text = serialize(document)
    assert json.loads(text)["format_version"] == 5
    assert parse_document(text) == document


@pytest.mark.parametrize(
    "text",
    [
        "",
        "not json",
        "[1, 2]",
        "{}",
        '{"palette_sequences": []}',
        '{"palette_sequences": [["#fff"]], "format_version": "x"}',
        '{"palette_sequences": [["#fff"]], "motif": [{"y": 1}]}',
        '{"palette_sequences": [["#fff"]], "unit_width": 0}',
    ],
)
def test_bad_files_give_a_friendly_error(text: str) -> None:
    with pytest.raises(OpenError) as caught:
        parse_document(text)
    assert caught.value.key == "file.error.notPattern"


def test_newer_files_say_so() -> None:
    data = PatternDocument().to_dict()
    data["format_version"] = 6
    with pytest.raises(OpenError) as caught:
        parse_document(json.dumps(data))
    assert caught.value.key == "file.error.tooNew"


# File names ------------------------------------------------------------


@pytest.mark.parametrize(
    ("given", "stem"),
    [
        ("flower-band.json", "flower-band"),
        ("Flower.JSON", "Flower"),
        ("C:\\patterns\\rose.json", "rose"),
        ("/a/b/my%20band.json", "my band"),
        ("notes.txt", "notes.txt"),
        ("  .json", ""),
    ],
)
def test_stem_of(given: str, stem: str) -> None:
    assert stem_of(given) == stem


def test_file_name() -> None:
    assert file_name("rose", ".json", "New pattern") == "rose.json"
    assert file_name("rose", ".png", "New pattern") == "rose.png"
    assert file_name(None, ".json", "Nytt mønster") == "Nytt mønster.json"
    assert file_name("a/b:c?", ".json", "x") == "a-b-c.json"
    assert file_name("  ", ".json", "") == "kvale.json"
    assert file_name("...", ".png", "///") == "kvale.png"


# Unsaved changes -------------------------------------------------------


def test_doc_session_tracks_unsaved_changes() -> None:
    document = PatternDocument()
    session = DocSession(document)
    assert session.name is None
    assert not session.is_dirty(document)
    assert session.display_name("New pattern") == "New pattern"

    document.set_mark(0, 0, 1)
    assert session.is_dirty(document)
    document.erase_mark(0, 0)
    assert not session.is_dirty(document)  # back to the saved state

    document.set_mark(0, 0, 1)
    session.mark_saved(document, "rose")
    assert not session.is_dirty(document)
    assert session.display_name("New pattern") == "rose.json"

    session.mark_saved(document)  # saving to the same file keeps the name
    assert session.name == "rose"

    other = load_document(EXAMPLE)
    session.reset(other, None)
    assert session.name is None
    assert not session.is_dirty(other)
    assert session.is_dirty(document)


# Autosave --------------------------------------------------------------


def test_autosave_round_trip() -> None:
    document = load_document(EXAMPLE)
    saved = fingerprint(serialize(PatternDocument()))
    text = autosave_payload(serialize(document), "flower-band", saved, 1_700_000_000_000.0)
    restored = read_autosave(text)
    assert restored is not None
    assert restored.document == document
    assert restored.name == "flower-band"
    assert restored.saved_fingerprint == saved
    assert restored.time_ms == 1_700_000_000_000.0

    session = DocSession(restored.document, restored.name)
    session.saved_fingerprint = restored.saved_fingerprint
    assert session.is_dirty(restored.document)  # the unsaved marker survives a reload


def test_autosave_untitled() -> None:
    text = autosave_payload(serialize(PatternDocument()), None, "abc", 1.0)
    restored = read_autosave(text)
    assert restored is not None and restored.name is None


@pytest.mark.parametrize(
    "text",
    [
        None,
        "",
        "garbage",
        "[]",
        '{"kvale_autosave": 99, "document": {}}',
        '{"kvale_autosave": 1}',
        '{"kvale_autosave": 1, "document": {"palette_sequences": []}}',
        '{"kvale_autosave": 1, "document": {"palette_sequences": [["#fff"]]}, "time": "x"}',
    ],
)
def test_unreadable_autosave_is_ignored(text: str | None) -> None:
    assert read_autosave(text) is None


# Patterns given in the URL ---------------------------------------------


def test_url_source_example() -> None:
    source = url_source("?example=flower-band", "")
    assert source == UrlSource("example", "flower-band")
    assert source.fetch_url() == "examples/flower-band.json"
    assert source.name == "flower-band"


@pytest.mark.parametrize("bad", ["../secret", "Flower", "a/b", "x" * 80, "%2e%2e"])
def test_url_source_rejects_odd_example_names(bad: str) -> None:
    assert url_source(f"?example={bad}", "") is None


def test_url_source_file() -> None:
    source = url_source("?file=https%3A%2F%2Fexample.org%2Fp%2Frose.json%3Fv%3D2", "")
    assert source == UrlSource("file", "https://example.org/p/rose.json?v=2")
    assert source.fetch_url() == "https://example.org/p/rose.json?v=2"
    assert source.name == "rose"
    assert url_source("?pattern=patterns/a.json", "") == UrlSource("file", "patterns/a.json")
    assert url_source("?file=javascript:alert(1)", "") is None
    assert url_source("?file=data:application/json,{}", "") is None
    assert UrlSource("file", "https://example.org/").name is None


def test_url_source_none() -> None:
    assert url_source("", "") is None
    assert url_source("?lang=en", "#top") is None
    assert url_source("?example=", "") is None


def test_data_hash_round_trip() -> None:
    text = serialize(load_document(EXAMPLE))
    fragment = encode_data_hash(text)
    source = url_source("", "#" + fragment)
    assert source is not None and source.kind == "data" and source.name is None
    assert parse_document(decode_data_hash(source.value)) == load_document(EXAMPLE)


@pytest.mark.parametrize("bad", ["!!!", "abc", "eJw"])
def test_damaged_data_hash(bad: str) -> None:
    with pytest.raises(OpenError):
        decode_data_hash(bad)


# PNG export ------------------------------------------------------------


def test_png_cell_size() -> None:
    assert png_cell_size(84, 24) == 16
    assert png_cell_size(1000, 10) == 8
    assert png_cell_size(100_000, 10) == 4
    assert png_cell_size(0, 0) == 16


def test_render_png_includes_ends_corners_and_backstitch() -> None:
    document = load_document(EXAMPLE)
    document.top_left_repeat_override = RepeatOverride(added_marks=[Mark(0, 0, 1)])
    data = render_png(document)
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    image = Image.open(io.BytesIO(data)).convert("RGB")
    grid = build_colour_grid(document)
    assert image.size == (len(grid[0]) * 16, len(grid) * 16)
    for x, y in [(0, 0), (5, 3), (len(grid[0]) - 1, len(grid) - 1)]:
        expected = tuple(bytes.fromhex(grid[y][x].lstrip("#")))
        assert image.getpixel((x * 16 + 8, y * 16 + 8)) == expected
