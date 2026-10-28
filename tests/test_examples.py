import json
from pathlib import Path

from kvale.core.renderer import build_colour_grid
from kvale.core.serialization import load_document

ROOT = Path(__file__).resolve().parent.parent


def test_flower_band_example_colour_grid_is_unchanged() -> None:
    # The expected grid was generated from examples/flower-band.json before the
    # editing logic moved into core, so any behaviour change shows up here.
    document = load_document(ROOT / "examples" / "flower-band.json")
    expected = json.loads((ROOT / "tests" / "data" / "flower-band-grid.json").read_text())

    assert build_colour_grid(document) == expected
