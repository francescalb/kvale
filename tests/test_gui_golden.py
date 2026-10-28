"""Replay the GUI sessions in gui_scenarios.py and compare with the branch.

Skipped when no display is available.
"""

from __future__ import annotations

import json
import tkinter as tk
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from gui_scenarios import SCENARIOS

from kvale.gui.app import KvaleApp

GOLDEN: dict[str, Any] = json.loads(
    (Path(__file__).resolve().parent / "data" / "golden" / "gui.json").read_text(encoding="utf-8")
)


@pytest.fixture
def app() -> Iterator[KvaleApp]:
    try:
        kvale_app = KvaleApp()
    except tk.TclError as error:
        pytest.skip(f"Tkinter cannot open a display: {error}")
    kvale_app.root.update()
    yield kvale_app
    kvale_app.root.destroy()


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_gui_scenario_matches_branch(name: str, app: KvaleApp) -> None:
    snapshots = SCENARIOS[name](app)
    expected = GOLDEN[name]
    assert len(snapshots) == len(expected)
    for index, (actual, wanted) in enumerate(zip(snapshots, expected, strict=True)):
        assert actual == wanted, f"{name}: snapshot {index} differs"
