"""Record tests/data/golden/gui.json by running gui_scenarios.py (needs a display).

Run once against the add_rm_col_rows branch (commit 0e46630) with that
branch installed in the Python environment:

    python tests/generate_gui_golden.py

Only run it again when a behaviour change is intended, and review the diff.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gui_scenarios import SCENARIOS

from kvale.gui.app import KvaleApp

OUTPUT = Path(__file__).resolve().parent / "data" / "golden" / "gui.json"


def main() -> None:
    result: dict[str, Any] = {}
    for name, scenario in SCENARIOS.items():
        app = KvaleApp()
        app.root.update()
        try:
            result[name] = scenario(app)
        finally:
            app.root.destroy()
    OUTPUT.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
