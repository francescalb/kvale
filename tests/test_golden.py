"""Golden tests that lock the behaviour of the add_rm_col_rows branch.

See golden_cases.py and generate_golden.py for where the expected data
comes from.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from kvale.core.model import PatternDocument
from kvale.core.renderer import build_backstitch_segments, build_colour_grid, render_image
from kvale.core.serialization import load_document, save_document

ROOT = Path(__file__).resolve().parent.parent
GOLDEN: dict[str, Any] = json.loads(
    (ROOT / "tests" / "data" / "golden" / "core.json").read_text(encoding="utf-8")
)


def _document(name: str) -> PatternDocument:
    return PatternDocument.from_dict(GOLDEN[name]["input"])


@pytest.mark.parametrize("name", sorted(GOLDEN))
def test_colour_grid(name: str) -> None:
    assert build_colour_grid(_document(name)) == GOLDEN[name]["grid"]


@pytest.mark.parametrize("name", sorted(GOLDEN))
def test_backstitch_segments(name: str) -> None:
    segments = [
        [s.start_x, s.start_y, s.end_x, s.end_y, s.colour]
        for s in build_backstitch_segments(_document(name))
    ]
    assert segments == GOLDEN[name]["backstitches"]


@pytest.mark.parametrize("name", sorted(GOLDEN))
@pytest.mark.parametrize(("key", "cell_size", "draw_grid"), [("render_18_grid", 18, True), ("render_7_plain", 7, False)])
def test_rendered_image(name: str, key: str, cell_size: int, draw_grid: bool) -> None:
    image = render_image(_document(name), cell_size=cell_size, draw_grid=draw_grid)
    expected = GOLDEN[name][key]
    assert list(image.size) == expected["size"]
    assert image.mode == expected["mode"]
    assert hashlib.sha256(image.tobytes()).hexdigest() == expected["sha256"]


@pytest.mark.parametrize("name", sorted(GOLDEN))
def test_to_dict(name: str) -> None:
    data = _document(name).to_dict()
    assert data == GOLDEN[name]["to_dict"]
    # Same key order as the branch, so saved files do not change on re-save.
    assert list(data) == list(GOLDEN[name]["to_dict"])


@pytest.mark.parametrize("name", sorted(GOLDEN))
def test_round_trip(name: str, tmp_path: Path) -> None:
    document = _document(name)
    assert PatternDocument.from_dict(document.to_dict()) == document

    path = tmp_path / "pattern.json"
    save_document(document, path)
    restored = load_document(path)
    assert restored == document
    assert build_colour_grid(restored) == GOLDEN[name]["grid"]


def test_format_version_is_four_for_old_files() -> None:
    # examples/flower-band.json predates format_version and backstitches.
    document = load_document(ROOT / "examples" / "flower-band.json")
    assert document.format_version == 4
    assert document.backstitches == []
    assert document.top_repeat_override is None
    assert document.to_dict()["format_version"] == 4
