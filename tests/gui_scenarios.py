"""Scripted GUI sessions used by test_gui_golden.py.

Each scenario drives the Tkinter app through the same handlers that the
widgets call and records a snapshot after every step. The expected snapshots
in tests/data/golden/gui.json were recorded from the add_rm_col_rows branch
(commit 0e46630) with generate_gui_golden.py, so the merged GUI must behave
exactly like that branch.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from tkinter import messagebox, ttk
from typing import Any

# KvaleApp is not imported here so the same scenarios can run against any
# version of the app; they only use handler names that both versions share.
App = Any
Snapshot = dict[str, Any]


def snapshot(app: App) -> Snapshot:
    return {
        "document": app.document.to_dict(),
        "unit_width": app.unit_width.get(),
        "unit_height": app.unit_height.get(),
        "symmetry": sorted(name for name, var in app.symmetry_vars.items() if var.get()),
        "edit_target": app.edit_target.get(),
        "extension": app.override_extension.get(),
        "active_colour": app.active_colour.get(),
        "status": app.status.get(),
    }


def _event(x: float, y: float) -> tk.Event[tk.Misc]:
    event: tk.Event[tk.Misc] = tk.Event()
    event.x = int(x)
    event.y = int(y)
    return event


def click_cell(app: App, x: int, y: int, button: int = 1) -> None:
    """Click the centre of local cell (x, y) in the current editor."""
    canvas = app.canvas
    event = _event(
        canvas.grid_origin_x + (x - canvas.editor_min_x) * canvas.cell_size + canvas.cell_size // 2,
        canvas.grid_origin_y + (y - canvas.editor_min_y) * canvas.cell_size + canvas.cell_size // 2,
    )
    if button == 1:
        canvas._paint(event)
    else:
        canvas._erase(event)


def click_point(app: App, x: float, y: float, button: int = 1) -> None:
    """Click local grid coordinate (x, y); integers are intersections."""
    canvas = app.canvas
    event = _event(
        canvas.grid_origin_x + (x - canvas.editor_min_x) * canvas.cell_size,
        canvas.grid_origin_y + (y - canvas.editor_min_y) * canvas.cell_size,
    )
    if button == 1:
        canvas._paint(event)
    else:
        canvas._erase(event)


def backstitch(app: App, start: tuple[int, int], end: tuple[int, int]) -> None:
    click_point(app, *start)
    click_point(app, *end)


def set_target(app: App, target: str) -> None:
    app.edit_target.set(target)
    app._change_edit_target()


def set_tool(app: App, tool: str) -> None:
    app.stitch_tool.set(tool)
    app._change_stitch_tool()


def set_symmetry(app: App, *operations: str) -> None:
    for name, variable in app.symmetry_vars.items():
        variable.set(name in operations)
    app._apply_symmetry()


def set_extension(app: App, extension: int) -> None:
    app.override_extension.set(extension)
    app._apply_override_extension()


@contextmanager
def patched_messagebox(answer: bool = True) -> Iterator[list[str]]:
    shown: list[str] = []
    saved = (messagebox.askyesno, messagebox.showinfo, messagebox.showerror)

    def ask(title: str, *_args: object, **_kwargs: object) -> bool:
        shown.append(title)
        return answer

    def show(title: str, *_args: object, **_kwargs: object) -> str:
        shown.append(title)
        return "ok"

    messagebox.askyesno = ask  # type: ignore[assignment]
    messagebox.showinfo = show  # type: ignore[assignment]
    messagebox.showerror = show  # type: ignore[assignment]
    try:
        yield shown
    finally:
        messagebox.askyesno, messagebox.showinfo, messagebox.showerror = saved


def _find_widgets(widget: tk.Misc, kind: type[tk.Misc]) -> list[Any]:
    found: list[Any] = []
    for child in widget.winfo_children():
        if isinstance(child, kind):
            found.append(child)
        found.extend(_find_widgets(child, kind))
    return found


def run_resize_dialog(app: App, action: str, target: str, number: int | None = None) -> None:
    """Open the row/column dialog, fill it in and press "Utfør"."""

    def drive() -> None:
        dialogs = [w for w in app.root.winfo_children() if isinstance(w, tk.Toplevel)]
        if not dialogs or dialogs[-1].grab_status() is None:
            app.root.after(20, drive)
            return
        dialog = dialogs[-1]
        action_combo, target_combo = _find_widgets(dialog, ttk.Combobox)
        action_combo.set(action)
        target_combo.set(target)
        if number is not None:
            (spin,) = _find_widgets(dialog, ttk.Spinbox)
            spin.set(str(number))
        (button,) = [b for b in _find_widgets(dialog, ttk.Button) if b.cget("text") == "Utfør"]
        button.invoke()

    app.root.after(20, drive)
    app._open_resize_grid_dialog()


def _record(app: App, steps: list[Callable[[], None]]) -> list[Snapshot]:
    snapshots = [snapshot(app)]
    for step in steps:
        step()
        app.root.update_idletasks()
        snapshots.append(snapshot(app))
    for action in [app.undo] * len(steps) + [app.redo] * len(steps):
        action()
        snapshots.append(snapshot(app))
    return snapshots


def scenario_unit_editing(app: App) -> list[Snapshot]:
    def paint(x: int, y: int, colour: int, button: int = 1) -> Callable[[], None]:
        def step() -> None:
            app.active_colour.set(colour)
            click_cell(app, x, y, button)

        return step

    return _record(
        app,
        [
            lambda: set_symmetry(app, "identity", "mirror_x"),
            paint(1, 1, 2),
            paint(10, 1, 2),  # same colour on a copy: no change
            paint(10, 1, 1),  # recolours the source mark
            paint(3, 4, 3),
            paint(8, 4, 0, button=3),  # erase a copy
            lambda: set_tool(app, "backstitch"),
            lambda: backstitch(app, (1, 1), (2, 3)),
            lambda: backstitch(app, (11, 1), (10, 3)),  # mirrored copy, same colour
            paint_backstitch_colour(app, 3, (11, 1), (10, 3)),  # recolour from the copy
            lambda: backstitch(app, (4, 4), (4, 4)),  # same point: nothing
            lambda: click_point(app, 10.5, 2.0, button=3),  # erase near the copy
            lambda: backstitch(app, (0, 0), (12, 12)),
            lambda: click_point(app, 6.1, 6.0, button=3),
            lambda: set_tool(app, "cross"),
            lambda: set_symmetry(app, "identity", "rotate_90", "diag_anti"),
            paint(2, 0, 1),
        ],
    )


def paint_backstitch_colour(
    app: App, colour: int, start: tuple[int, int], end: tuple[int, int]
) -> Callable[[], None]:
    def step() -> None:
        app.active_colour.set(colour)
        backstitch(app, start, end)

    return step


def scenario_end_pieces(app: App) -> list[Snapshot]:
    steps: list[Callable[[], None]] = [
        lambda: set_symmetry(app, "identity", "mirror_x"),
        lambda: app.active_colour.set(0),
        lambda: click_cell(app, 1, 0),
        lambda: click_cell(app, 2, 2),
        lambda: set_tool(app, "backstitch"),
        lambda: backstitch(app, (0, 3), (3, 3)),
        lambda: set_tool(app, "cross"),
    ]

    def edge_steps(edge: str, outside: tuple[int, int], stitch: tuple[tuple[int, int], tuple[int, int]]) -> None:
        steps.extend(
            [
                lambda: set_target(app, edge),
                lambda: app.active_colour.set(1),
                lambda: click_cell(app, 1, 0),  # recolour base cell -> added mark
                lambda: app.active_colour.set(0),
                lambda: click_cell(app, 10, 0),  # base colour already: no change
                lambda: click_cell(app, 1, 0),  # back to base colour -> addition removed
                lambda: click_cell(app, 2, 2, button=3),  # hide a base cell
                lambda: click_cell(app, 2, 2, button=3),  # already hidden: no change
                lambda: click_cell(app, 2, 2),  # restore with base colour
                lambda: click_cell(app, 9, 2, button=3),
                lambda: click_cell(app, 5, 5),  # add on empty cell
                lambda: click_cell(app, 6, 6, button=3),  # erase empty: no change
                lambda: set_extension(app, 2),
                lambda: app.active_colour.set(2),
                lambda: click_cell(app, *outside),
                lambda: set_tool(app, "backstitch"),
                lambda: backstitch(app, *stitch),
                lambda: backstitch(app, (0, 3), (3, 3)),  # base stitch, same colour: no change
                lambda: app.active_colour.set(3),
                lambda: backstitch(app, (8, 3), (11, 3)),  # recolour mirrored base stitch
                lambda: app.active_colour.set(0),
                lambda: backstitch(app, (8, 3), (11, 3)),  # back to base colour: restore
                lambda: click_point(app, 1.5, 3.0, button=3),  # hide base stitch
                lambda: set_tool(app, "cross"),
                lambda: click_cell(app, *outside, button=3),
                lambda: app.active_colour.set(1),
                lambda: click_cell(app, *outside),
                lambda: set_extension(app, 1),  # trims marks/stitches outside
                lambda: set_extension(app, 1),  # unchanged
            ]
        )

    edge_steps("top", (4, -2), ((0, -2), (2, 0)))
    edge_steps("bottom", (4, 13), ((0, 14), (2, 12)))
    edge_steps("left", (-2, 4), ((-2, 0), (0, 2)))
    edge_steps("right", (13, 4), ((14, 0), (12, 2)))

    def reset(answer: bool) -> Callable[[], None]:
        def step() -> None:
            with patched_messagebox(answer):
                app._reset_selected_override()

        return step

    steps.extend(
        [
            reset(False),
            reset(True),
            lambda: set_target(app, "top"),
            lambda: app.mode.set("preview"),
            lambda: app._change_mode(),
            lambda: set_target(app, "unit"),
        ]
    )
    return _record(app, steps)


def scenario_resize(app: App) -> list[Snapshot]:
    def resize(axis: str, index: int, insertion: bool) -> Callable[[], None]:
        def step() -> None:
            with patched_messagebox():
                app._resize_grid_axis(axis, index, insertion=insertion)

        return step

    def dialog(action: str, target: str, number: int | None = None) -> Callable[[], None]:
        def step() -> None:
            with patched_messagebox():
                run_resize_dialog(app, action, target, number)

        return step

    def controls(width: int, height: int, **flags: bool) -> Callable[[], None]:
        def step() -> None:
            app.unit_width.set(width)
            app.unit_height.set(height)
            for name, value in flags.items():
                getattr(app, name).set(value)
            with patched_messagebox():
                app._apply_controls()

        return step

    steps: list[Callable[[], None]] = [
        lambda: set_symmetry(app, "identity", "mirror_x", "mirror_y", "rotate_90"),
        lambda: app.active_colour.set(1),
        lambda: click_cell(app, 1, 2),
        lambda: click_cell(app, 4, 0),
        lambda: set_tool(app, "backstitch"),
        lambda: backstitch(app, (1, 1), (3, 2)),
        lambda: set_tool(app, "cross"),
        lambda: set_target(app, "right"),
        lambda: set_extension(app, 2),
        lambda: click_cell(app, 13, 1),
        lambda: click_cell(app, 1, 2, button=3),
        lambda: set_tool(app, "backstitch"),
        lambda: backstitch(app, (12, 0), (14, 2)),
        lambda: click_point(app, 2.0, 1.5, button=3),
        lambda: set_tool(app, "cross"),
        lambda: set_target(app, "bottom"),
        lambda: set_extension(app, 1),
        lambda: click_cell(app, 3, 12),
        lambda: click_cell(app, 4, 3),
        lambda: set_target(app, "unit"),
        resize("column", 0, True),  # symmetry adds columns and rows
        resize("row", 3, False),
        dialog("Legg til", "Siste kolonne"),
        dialog("Fjern", "Øverste rad"),
        dialog("Legg til", "Rad med nummer", 3),
        dialog("Fjern", "Kolonne med nummer", 2),
        lambda: set_symmetry(app, "identity"),
        dialog("Legg til", "Nederste rad"),
        dialog("Fjern", "Første kolonne"),
        dialog("Legg til", "Kolonne med nummer", 99),
        dialog("Fjern", "Rad med nummer", 1),
        controls(9, 7),
        controls(14, 10, repeat_left_column=False, repeat_bottom_row=False),
        controls(5, 5),
        lambda: set_symmetry(app, "identity", "diag_main"),
        controls(5, 6),
        controls(1, 1),
        resize("column", 0, False),  # cannot remove the last column
    ]
    return _record(app, steps)


def scenario_palette_and_files(app: App) -> list[Snapshot]:
    import importlib
    from pathlib import Path

    app_module = importlib.import_module("kvale.gui.app")
    example = Path(__file__).resolve().parent.parent / "examples" / "flower-band.json"

    def answer(name: str, value: str | None) -> None:
        setattr(app_module, name, lambda *_args, **_kwargs: value)

    def add_colour(value: str | None) -> Callable[[], None]:
        def step() -> None:
            answer("ask_rgb_colour", value)
            app._add_palette_colour()

        return step

    def add_dmc(value: str | None) -> Callable[[], None]:
        def step() -> None:
            answer("ask_dmc_colour", value)
            app._add_dmc_palette_colour()

        return step

    def choose_sequence(index: int, sequence: list[str] | None) -> Callable[[], None]:
        def step() -> None:
            app._open_palette_sequence_dialog = lambda *_args: None if sequence is None else list(sequence)
            app._choose_palette_colour(index)

        return step

    def use_sequence(value: bool) -> Callable[[], None]:
        def step() -> None:
            app.use_palette_sequence.set(value)
            app._on_use_palette_sequence_changed()

        return step

    def paint(x: int, y: int, colour: int) -> Callable[[], None]:
        def step() -> None:
            app._select_palette_colour(colour)
            click_cell(app, x, y)

        return step

    saved = {name: getattr(app_module, name) for name in ("ask_rgb_colour", "ask_dmc_colour")}
    try:
        return _record(
            app,
            [
                add_colour("#123456"),
                add_colour(None),
                add_dmc("#fedcba"),
                add_dmc(None),
                paint(2, 2, 5),
                choose_sequence(5, ["#fedcba", "#000001", "#000002"]),
                choose_sequence(5, ["#fedcba", "#000001", "#000002"]),  # unchanged
                choose_sequence(1, None),  # cancelled
                use_sequence(True),
                use_sequence(True),
                lambda: app._select_palette_colour(4),
                paint(3, 3, 1),
            ],
        ) + _record(
            app,
            [
                lambda: app._load_document_path(example),
                paint(0, 0, 2),
                use_sequence(True),
                lambda: app.new_document(),
                paint(1, 1, 3),
            ],
        )
    finally:
        for name, value in saved.items():
            setattr(app_module, name, value)


SCENARIOS: dict[str, Callable[[App], list[Snapshot]]] = {
    "unit-editing": scenario_unit_editing,
    "end-pieces": scenario_end_pieces,
    "resize": scenario_resize,
    "palette-and-files": scenario_palette_and_files,
}
