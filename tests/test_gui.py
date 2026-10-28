"""Smoke tests for the Tkinter GUI. Skipped when no display is available."""

import tkinter as tk
from collections.abc import Iterator
from tkinter import messagebox

import pytest
from gui_scenarios import (
    backstitch,
    click_cell,
    click_point,
    run_resize_dialog,
    set_extension,
    set_symmetry,
    set_target,
    set_tool,
)

from kvale.core.model import Backstitch, Cell, Mark
from kvale.core.renderer import build_colour_grid
from kvale.gui import app as app_module
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
    app._insert_column_at(0)
    assert app.unit_width.get() == 13
    assert app.unit_height.get() == 12

    # A quarter turn maps the new column onto rows, so the unit stays square
    # and keeps its symmetry.
    app.unit_width.set(12)
    app._apply_controls()
    app.symmetry_vars["rotate_90"].set(True)
    app._apply_symmetry()
    app._insert_column_at(0)

    assert (app.unit_width.get(), app.unit_height.get()) == (14, 14)
    assert app.symmetry_vars["rotate_90"].get()
    app.undo()
    assert (app.unit_width.get(), app.unit_height.get()) == (12, 12)
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
    monkeypatch.setattr(app_module, "ask_rgb_colour", lambda *_args, **_kwargs: "#010203")

    app._add_palette_colour()
    app.active_colour.set(4)
    assert app.document.palette_sequences[-1] == ["#010203"]

    app.undo()
    assert len(app.document.palette_sequences) == 4
    assert app.active_colour.get() == 0


def test_end_piece_editing_with_extension(app: KvaleApp, monkeypatch: pytest.MonkeyPatch) -> None:
    app.active_colour.set(1)
    _click_cell(app, 2, 2)
    set_target(app, "bottom")
    set_extension(app, 2)
    assert app.canvas.editor_min_y == 0

    click_cell(app, 2, 2, button=3)  # hide the unit cell in the end piece
    click_cell(app, 4, 13)  # paint in the extension
    override = app.document.bottom_repeat_override
    assert override is not None
    assert override.extension == 2
    assert override.removed_cells == [Cell(2, 2)]
    assert override.added_marks == [Mark(4, 13, 1)]
    assert len(build_colour_grid(app.document)) == 24 + 2

    monkeypatch.setattr(messagebox, "askyesno", lambda *_args, **_kwargs: True)
    app._reset_selected_override()
    assert app.document.bottom_repeat_override is None
    app.undo()
    assert app.document.bottom_repeat_override == override


def test_backstitch_tool(app: KvaleApp) -> None:
    set_tool(app, "backstitch")
    app.active_colour.set(2)
    backstitch(app, (1, 1), (3, 2))
    assert app.document.backstitches == [Backstitch(1, 1, 3, 2, 2)]

    click_point(app, 2.0, 1.5, button=3)
    assert app.document.backstitches == []
    app.undo()
    assert app.document.backstitches == [Backstitch(1, 1, 3, 2, 2)]


def test_resize_dialog(app: KvaleApp) -> None:
    set_symmetry(app, "identity", "mirror_x")
    run_resize_dialog(app, "Legg til", "Kolonne med nummer", 2)
    assert (app.document.unit_width, app.unit_width.get()) == (14, 14)

    run_resize_dialog(app, "Fjern", "Nederste rad")
    assert app.document.unit_height == 11
    assert app.status.get() == "Endret"
