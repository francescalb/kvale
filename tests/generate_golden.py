"""Generate tests/data/golden/core.json from the cases in golden_cases.py.

This was run once against the add_rm_col_rows branch (commit 0e46630) to lock
its behaviour before the merge:

    python tests/generate_golden.py   # with commit 0e46630 installed

Only run it again when a behaviour change is intended, and review the diff.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from golden_cases import CASES

from kvale.core.model import PatternDocument
from kvale.core.renderer import (
    build_backstitch_segments,
    build_colour_grid,
    render_image,
)

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "tests" / "data" / "golden" / "core.json"


def image_digest(document: PatternDocument, cell_size: int, draw_grid: bool) -> dict[str, Any]:
    image = render_image(document, cell_size=cell_size, draw_grid=draw_grid)
    return {
        "size": list(image.size),
        "mode": image.mode,
        "sha256": hashlib.sha256(image.tobytes()).hexdigest(),
    }


def describe(document: PatternDocument) -> dict[str, Any]:
    return {
        "to_dict": document.to_dict(),
        "grid": build_colour_grid(document),
        "backstitches": [
            [s.start_x, s.start_y, s.end_x, s.end_y, s.colour]
            for s in build_backstitch_segments(document)
        ],
        "render_18_grid": image_digest(document, 18, True),
        "render_7_plain": image_digest(document, 7, False),
    }


def main() -> None:
    result: dict[str, Any] = {}
    for name, data in CASES.items():
        result[name] = {"input": data, **describe(PatternDocument.from_dict(data))}
    flower = json.loads((ROOT / "examples" / "flower-band.json").read_text(encoding="utf-8"))
    result["flower-band"] = {"input": flower, **describe(PatternDocument.from_dict(flower))}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
