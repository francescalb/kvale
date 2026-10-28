"""Smoke tests for the Tkinter GUI. Skipped when no display is available."""

import tkinter as tk
from collections.abc import Iterator
from tkinter import colorchooser, messagebox

import pytest

from kvale.core.model import Mark
from kvale.gui.app import KvaleApp


@pytest.fixture
def app() -> Iterator[KvaleApp]:
    try:
        kvale_app = KvaleApp()
    except tk.TclError as error:
        pytest.skip(f"Tkinter cannot open a display: {error}")
    kvale_app.root.update()
    yield kvale_app
    kvale_app.root.destroy()


def _click_cell(kvale_app: KvaleApp, x: int, y: int, button: int = 1) -> None:
    canvas = kvale_app.canvas
    event: tk.Event[tk.Misc] = tk.Event()
    event.x = canvas.grid_origin_x + x * canvas.cell_size + canvas.cell_size // 2
    event.y = canvas.grid_origin_y + y * canvas.cell_size + canvas.cell_size // 2
    if button == 1:
        canvas._paint(event)
    else:
        canvas._erase(event)


def test_paint_copy_edits_source_and_undo_redo(app: KvaleApp) -> None:
    app.symmetry_vars["mirror_x"].set(True)
    app._apply_symmetry()
    app.active_colour.set(2)

    _click_cell(app, 1, 1)
    assert app.document.motif == [Mark(1, 1, 2)]

    app.active_colour.set(1)
    _click_cell(app, 10, 1)  # mirrored copy of (1, 1) in a 12-wide unit
    assert app.document.motif == [Mark(1, 1, 1)]

    app.undo()
    assert app.document.motif == [Mark(1, 1, 2)]
    app.redo()
    assert app.document.motif == [Mark(1, 1, 1)]

    _click_cell(app, 10, 1, button=3)
    assert app.document.motif == []
    assert app.status.get() == "Endret"


def test_insert_column_updates_controls_and_undo(app: KvaleApp) -> None:
    app.symmetry_vars["rotate_90"].set(True)
    app._apply_symmetry()

    app._insert_column_at(0)

    assert app.unit_width.get() == 13
    assert not app.symmetry_vars["rotate_90"].get()
    app.undo()
    assert app.unit_width.get() == 12
    assert app.symmetry_vars["rotate_90"].get()


def test_square_only_symmetry_shows_message(app: KvaleApp, monkeypatch: pytest.MonkeyPatch) -> None:
    messages: list[str] = []
    monkeypatch.setattr(messagebox, "showinfo", lambda title, _text: messages.append(title))
    app.unit_height.set(8)
    app._apply_controls()

    app.symmetry_vars["diag_main"].set(True)
    app.symmetry_vars["identity"].set(False)
    app._apply_symmetry()

    assert messages == ["Kvadratisk enhet kreves"]
    assert app.document.symmetry == ["identity"]
    assert app.symmetry_vars["identity"].get()
    assert not app.symmetry_vars["diag_main"].get()


def test_add_colour_and_undo_keeps_valid_selection(app: KvaleApp, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(colorchooser, "askcolor", lambda **_kwargs: ((0, 0, 0), "#010203"))

    app._add_palette_colour()
    app.active_colour.set(4)
    assert app.document.palette_sequences[-1] == ["#010203"]

    app.undo()
    assert len(app.document.palette_sequences) == 4
    assert app.active_colour.get() == 0
