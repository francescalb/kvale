from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import cast

from kvale.core.editing import (
    MAX_SEQUENCE_LENGTH,
    Axis,
    GridPlace,
    Target,
    can_remove_grid_line,
    get_end_piece,
    grid_line_for_place,
    max_line_number,
    resize_sequence,
)
from kvale.core.editor import Editor
from kvale.core.model import PatternDocument, RepeatOverride
from kvale.core.renderer import render_image
from kvale.core.serialization import load_document, save_document
from kvale.gui.canvas import PatternCanvas
from kvale.gui.dmc_palette import ask_dmc_colour
from kvale.gui.palette_button import PaletteButton, ask_rgb_colour


class KvaleApp:
    HISTORY_LIMIT = 100

    def __init__(self, initial_path: Path | None = None) -> None:
        self.root = tk.Tk()
        self.root.title("Kvale")
        self.root.geometry("1180x760")
        self.editor = Editor(history_limit=self.HISTORY_LIMIT)
        self.current_path: Path | None = None
        self.active_colour = tk.IntVar(value=0)
        self.mode = tk.StringVar(value="edit")
        self.stitch_tool = tk.StringVar(value="cross")
        self.status = tk.StringVar(value="Klar")
        self.symmetry_vars: dict[str, tk.BooleanVar] = {}
        self.palette_buttons: list[PaletteButton] = []
        self._palette_single_click_after_id: str | None = None
        self._build_ui()
        self._sync_controls_from_document()
        self.canvas.redraw()
        if initial_path is not None:
            try:
                self._load_document_path(initial_path)
            except (OSError, ValueError) as error:
                messagebox.showerror("Kunne ikke åpne mønster", str(error))

    @property
    def document(self) -> PatternDocument:
        # Undo and redo replace the document object, so always read it from the editor.
        return self.editor.document

    def run(self) -> None:
        self.root.mainloop()

    def _build_ui(self) -> None:
        self._build_menu()
        main = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True)

        sidebar_container = ttk.Frame(main)
        sidebar_canvas = tk.Canvas(sidebar_container, highlightthickness=0)
        sidebar_scroll = ttk.Scrollbar(sidebar_container, orient="vertical", command=sidebar_canvas.yview)
        sidebar = ttk.Frame(sidebar_canvas, padding=10)
        sidebar_canvas.configure(yscrollcommand=sidebar_scroll.set)
        sidebar_canvas.create_window((0,0), window=sidebar, anchor="nw")
        sidebar.bind("<Configure>", lambda e: sidebar_canvas.configure(scrollregion=sidebar_canvas.bbox("all")))
        sidebar_canvas.bind("<Configure>", lambda e: sidebar_canvas.itemconfigure(1, width=e.width))
        def _mw(event: tk.Event[tk.Misc]) -> None:
            sidebar_canvas.yview_scroll(int(-(event.delta / 120)), "units")
        sidebar_canvas.bind("<Enter>", lambda e: sidebar_canvas.bind_all("<MouseWheel>", _mw))
        sidebar_canvas.bind("<Leave>", lambda e: sidebar_canvas.unbind_all("<MouseWheel>"))
        sidebar_canvas.pack(side="left", fill="both", expand=True)
        sidebar_scroll.pack(side="right", fill="y")
        workspace = ttk.Frame(main, padding=8)
        main.add(sidebar_container, weight=0)
        main.add(workspace, weight=1)

        self._build_document_controls(sidebar)
        self._build_override_controls(sidebar)
        self._build_palette_controls(sidebar)
        self._build_symmetry_controls(sidebar)

        toolbar = ttk.Frame(workspace)
        toolbar.pack(fill=tk.X, pady=(0, 6))
        ttk.Radiobutton(
            toolbar, text="Rediger mønster", variable=self.mode, value="edit", command=self._change_mode
        ).pack(side=tk.LEFT)
        ttk.Radiobutton(
            toolbar, text="Se repetisjoner", variable=self.mode, value="preview", command=self._change_mode
        ).pack(side=tk.LEFT, padx=12)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=(2, 10))
        ttk.Radiobutton(
            toolbar,
            text="Korssting",
            variable=self.stitch_tool,
            value="cross",
            command=self._change_stitch_tool,
        ).pack(side=tk.LEFT)
        ttk.Radiobutton(
            toolbar,
            text="Attersting",
            variable=self.stitch_tool,
            value="backstitch",
            command=self._change_stitch_tool,
        ).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(
            toolbar,
            text="Venstre: farg/legg til, hoyre: slett.",
        ).pack(side=tk.RIGHT)

        self.canvas = PatternCanvas(
            workspace,
            editor=self.editor,
            active_colour_getter=self.active_colour.get,
            on_change=self._document_changed,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        ttk.Label(self.root, textvariable=self.status, anchor=tk.W, relief=tk.SUNKEN).pack(fill=tk.X)

    def _build_menu(self) -> None:
        menu = tk.Menu(self.root)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="Ny", command=self.new_document, accelerator="Ctrl+N")
        file_menu.add_command(label="Åpne...", command=self.open_document, accelerator="Ctrl+O")
        file_menu.add_command(label="Lagre", command=self.save_document, accelerator="Ctrl+S")
        file_menu.add_command(label="Lagre som...", command=self.save_document_as)
        file_menu.add_separator()
        file_menu.add_command(label="Eksporter PNG...", command=self.export_png)
        file_menu.add_separator()
        file_menu.add_command(label="Avslutt", command=self.root.destroy)
        menu.add_cascade(label="Fil", menu=file_menu)
        self.edit_menu = tk.Menu(menu, tearoff=False)
        self.edit_menu.add_command(label="Angre", command=self.undo, accelerator="Ctrl+Z")
        self.edit_menu.add_command(label="Gjør om", command=self.redo, accelerator="Ctrl+Y")
        menu.add_cascade(label="Rediger", menu=self.edit_menu)
        grid_menu = tk.Menu(menu, tearoff=False)
        grid_menu.add_command(label="Legg til/fjern rad eller kolonne...", command=self._open_resize_grid_dialog)
        menu.add_cascade(label="Rutenett", menu=grid_menu)
        self.root.config(menu=menu)
        self.root.bind("<Control-n>", lambda _event: self.new_document())
        self.root.bind("<Control-o>", lambda _event: self.open_document())
        self.root.bind("<Control-s>", lambda _event: self.save_document())
        self.root.bind("<Control-z>", lambda _event: self._run_history_shortcut(self.undo))
        self.root.bind("<Control-y>", lambda _event: self._run_history_shortcut(self.redo))
        self.root.bind("<Control-Shift-Z>", lambda _event: self._run_history_shortcut(self.redo))
        self.root.bind("<Control-Shift-z>", lambda _event: self._run_history_shortcut(self.redo))
        self._update_undo_redo_controls()

    def _spin_row(self, parent: tk.Misc, label: str, variable: tk.IntVar, row: int) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Spinbox(parent, from_=1, to=100, textvariable=variable, width=7, command=self._apply_controls).grid(
            row=row, column=1, sticky=tk.E, pady=2
        )

    def _build_document_controls(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Rutenett", padding=8)
        frame.pack(fill=tk.X, pady=(0, 8))
        self.unit_width = tk.IntVar(value=12)
        self.unit_height = tk.IntVar(value=12)
        self.repeats_x = tk.IntVar(value=6)
        self.repeats_y = tk.IntVar(value=2)
        self.repeat_left_column = tk.BooleanVar(value=True)
        self.repeat_right_column = tk.BooleanVar(value=True)
        self.repeat_top_row = tk.BooleanVar(value=True)
        self.repeat_bottom_row = tk.BooleanVar(value=True)
        self._spin_row(frame, "Bredde enhetscelle", self.unit_width, 0)
        self._spin_row(frame, "Høyde enhetscelle", self.unit_height, 1)
        self._spin_row(frame, "Repetisjoner horisontalt", self.repeats_x, 2)
        self._spin_row(frame, "Repetisjoner vertikalt", self.repeats_y, 3)

        ttk.Label(frame, text="Ytre kolonne/rad del av enhetscellen?").grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=(6, 2))
        ttk.Checkbutton(
            frame,
            text="Venstre kolonne",
            variable=self.repeat_left_column,
            command=self._apply_controls,
        ).grid(
            row=5, column=0, columnspan=2, sticky=tk.W
        )
        ttk.Checkbutton(
            frame,
            text="Høyre kolonne",
            variable=self.repeat_right_column,
            command=self._apply_controls,
        ).grid(
            row=6, column=0, columnspan=2, sticky=tk.W
        )
        ttk.Checkbutton(
            frame,
            text="Øverste rad",
            variable=self.repeat_top_row,
            command=self._apply_controls,
        ).grid(
            row=7, column=0, columnspan=2, sticky=tk.W
        )
        ttk.Checkbutton(
            frame,
            text="Nederste rad",
            variable=self.repeat_bottom_row,
            command=self._apply_controls,
        ).grid(
            row=8, column=0, columnspan=2, sticky=tk.W
        )

        ttk.Button(frame, text="Bruk", command=self._apply_controls).grid(
            row=9, column=0, columnspan=2, sticky=tk.EW, pady=(8, 0)
        )
        ttk.Button(
            frame,
            text="Legg til/fjern rad eller kolonne...",
            command=self._open_resize_grid_dialog,
        ).grid(row=10, column=0, columnspan=2, sticky=tk.EW, pady=(6, 0))

    def _build_override_controls(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Endestykker", padding=8)
        frame.pack(fill=tk.X, pady=(0, 8))
        self.edit_target = tk.StringVar(value="unit")
        self.override_extension = tk.IntVar(value=0)

        ttk.Radiobutton(
            frame,
            text="Repeterende enhet",
            variable=self.edit_target,
            value="unit",
            command=self._change_edit_target,
        ).grid(row=0, column=0, columnspan=2, sticky=tk.W)
        ttk.Radiobutton(
            frame,
            text="Øverste repetisjon",
            variable=self.edit_target,
            value="top",
            command=self._change_edit_target,
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W)
        ttk.Radiobutton(
            frame,
            text="Nederste repetisjon",
            variable=self.edit_target,
            value="bottom",
            command=self._change_edit_target,
        ).grid(row=2, column=0, columnspan=2, sticky=tk.W)
        ttk.Radiobutton(
            frame,
            text="Venstre repetisjon",
            variable=self.edit_target,
            value="left",
            command=self._change_edit_target,
        ).grid(row=3, column=0, columnspan=2, sticky=tk.W)
        ttk.Radiobutton(
            frame,
            text="Høyre repetisjon",
            variable=self.edit_target,
            value="right",
            command=self._change_edit_target,
        ).grid(row=4, column=0, columnspan=2, sticky=tk.W)

        self.override_extension_label = ttk.Label(frame, text="Ekstra rader utover")
        self.override_extension_label.grid(row=5, column=0, sticky=tk.W, pady=(6, 2))
        self.override_extension_spin = ttk.Spinbox(
            frame,
            from_=0,
            to=100,
            width=7,
            textvariable=self.override_extension,
        )
        self.override_extension_spin.grid(row=5, column=1, sticky=tk.E, pady=(6, 2))
        self.override_extension_button = ttk.Button(
            frame,
            text="Bruk ekstra rader",
            command=self._apply_override_extension,
        )
        self.override_extension_button.grid(row=6, column=0, columnspan=2, sticky=tk.EW, pady=(4, 0))
        self.override_reset_button = ttk.Button(
            frame,
            text="Nullstill valgt endestykke",
            command=self._reset_selected_override,
        )
        self.override_reset_button.grid(row=7, column=0, columnspan=2, sticky=tk.EW, pady=(4, 0))
        self._sync_override_controls()

    def _selected_target(self) -> Target:
        return cast(Target, self.edit_target.get())

    def _selected_override(self) -> RepeatOverride | None:
        target = self._selected_target()
        if target == "unit":
            return None
        return get_end_piece(self.document, target)

    def _sync_override_controls(self) -> None:
        if not hasattr(self, "edit_target"):
            return
        target = self.edit_target.get()
        override = self._selected_override()
        self.override_extension.set(override.extension if override else 0)
        horizontal = target in {"left", "right"}
        self.override_extension_label.configure(
            text="Ekstra kolonner utover" if horizontal else "Ekstra rader utover"
        )
        self.override_extension_button.configure(
            text="Bruk ekstra kolonner" if horizontal else "Bruk ekstra rader"
        )
        state = tk.NORMAL if target != "unit" else tk.DISABLED
        self.override_extension_label.configure(state=state)
        self.override_extension_spin.configure(state=state)
        self.override_extension_button.configure(state=state)
        self.override_reset_button.configure(state=state)

    def _change_edit_target(self) -> None:
        self._sync_override_controls()
        self.mode.set("edit")
        if hasattr(self, "canvas"):
            self.canvas.set_edit_target(self._selected_target())
            self.canvas.set_mode("edit")

    def _apply_override_extension(self) -> None:
        target = self._selected_target()
        if target == "unit":
            return
        try:
            extension = max(0, int(self.override_extension.get()))
        except (tk.TclError, ValueError) as error:
            messagebox.showerror("Ugyldig antall rader", str(error))
            return
        if self.editor.set_end_piece_extension(target, extension).changed:
            self._document_changed()

    def _reset_selected_override(self) -> None:
        target = self._selected_target()
        if target == "unit" or self._selected_override() is None:
            return
        if not messagebox.askyesno(
            "Nullstill endestykke",
            "Fjerne alle tillegg, skjulte celler og ekstra rader i dette endestykket?",
        ):
            return
        self.editor.reset_end_piece(target)
        self._sync_override_controls()
        self._document_changed()

    def _build_palette_controls(self, parent: ttk.Frame) -> None:
        self.palette_frame = ttk.LabelFrame(parent, text="Farger", padding=8)
        self.palette_frame.pack(fill=tk.X, pady=(0, 8))
        self.use_palette_sequence = tk.BooleanVar(value=False)

        list_container = ttk.Frame(self.palette_frame)
        list_container.pack(fill=tk.X, expand=True)
        self.palette_canvas = tk.Canvas(
            list_container,
            width=178,
            height=240,
            highlightthickness=0,
            borderwidth=0,
        )
        palette_scroll = ttk.Scrollbar(
            list_container,
            orient=tk.VERTICAL,
            command=self.palette_canvas.yview,
        )
        self.palette_canvas.configure(yscrollcommand=palette_scroll.set)
        self.palette_items = ttk.Frame(self.palette_canvas)
        self.palette_window = self.palette_canvas.create_window(
            (0, 0),
            window=self.palette_items,
            anchor=tk.NW,
        )
        self.palette_items.bind(
            "<Configure>",
            lambda _event: self.palette_canvas.configure(scrollregion=self.palette_canvas.bbox("all")),
        )
        self.palette_canvas.bind(
            "<Configure>",
            lambda event: self.palette_canvas.itemconfigure(self.palette_window, width=event.width),
        )
        self.palette_canvas.pack(side=tk.LEFT, fill=tk.X, expand=True)
        palette_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        ttk.Button(
            self.palette_frame,
            text="Legg til farge",
            command=self._add_palette_colour,
        ).pack(fill=tk.X, pady=(6, 0))
        ttk.Button(
            self.palette_frame,
            text="Legg til DMC-farge…",
            command=self._add_dmc_palette_colour,
        ).pack(fill=tk.X, pady=(4, 0))
        ttk.Checkbutton(
            self.palette_frame,
            text="Bruk fargeskvens",
            variable=self.use_palette_sequence,
            command=self._on_use_palette_sequence_changed,
        ).pack(anchor=tk.W, pady=(6, 0))
        self._rebuild_palette_buttons()

    def _rebuild_palette_buttons(self) -> None:
        for child in self.palette_items.winfo_children():
            child.destroy()

        selected_index = self.active_colour.get()
        self.palette_buttons = []

        for index, sequence in enumerate(self.document.palette_sequences):
            row = index
            is_selected = index == selected_index

            button = PaletteButton(
                self.palette_items,
                colour=sequence[0],
                colours=sequence,
                text=f"Farge {index + 1}",
                selected=is_selected,
                command=self._make_palette_select_command(index),
                edit_command=self._make_palette_edit_command(index),
                width=164,
                height=36,
            )
            button.grid(row=row, column=0, sticky=tk.EW, pady=2)
            button.bind("<MouseWheel>", self._scroll_palette)
            button.bind("<Button-4>", self._scroll_palette)
            button.bind("<Button-5>", self._scroll_palette)
            self.palette_buttons.append(button)
        self.palette_items.columnconfigure(0, weight=1)
        self.root.after_idle(self._finish_palette_rebuild)

    def _scroll_palette(self, event: tk.Event[tk.Misc]) -> str:
        if getattr(event, "num", None) == 4:
            direction = -1
        elif getattr(event, "num", None) == 5:
            direction = 1
        else:
            direction = -1 if event.delta > 0 else 1
        self.palette_canvas.yview_scroll(direction, "units")
        return "break"

    def _finish_palette_rebuild(self) -> None:
        self.palette_canvas.configure(scrollregion=self.palette_canvas.bbox("all"))
        selected = self.active_colour.get()
        if not self.palette_buttons or selected < 0 or selected >= len(self.palette_buttons):
            return
        total_height = max(1, self.palette_items.winfo_reqheight())
        visible_height = max(1, self.palette_canvas.winfo_height())
        item_top = self.palette_buttons[selected].winfo_y()
        item_bottom = item_top + self.palette_buttons[selected].winfo_height()
        view_top = self.palette_canvas.canvasy(0)
        view_bottom = view_top + visible_height
        if item_top < view_top:
            self.palette_canvas.yview_moveto(item_top / total_height)
        elif item_bottom > view_bottom:
            self.palette_canvas.yview_moveto(max(0.0, (item_bottom - visible_height) / total_height))

    def _on_palette_single_click(self, index: int) -> None:
        if self._palette_single_click_after_id is not None:
            self.root.after_cancel(self._palette_single_click_after_id)
        # Defer selection so double-click can cancel this redraw.
        self._palette_single_click_after_id = self.root.after(220, lambda: self._run_palette_single_click(index))

    def _make_palette_single_click_handler(self, index: int) -> Callable[[tk.Event[tk.Misc]], None]:
        def handler(_event: tk.Event[tk.Misc]) -> None:
            self._on_palette_single_click(index)

        return handler

    def _make_palette_double_click_handler(self, index: int) -> Callable[[tk.Event[tk.Misc]], None]:
        def handler(_event: tk.Event[tk.Misc]) -> None:
            self._on_palette_swatch_double_click(index)

        return handler

    def _run_palette_single_click(self, index: int) -> None:
        self._palette_single_click_after_id = None
        self._select_palette_colour(index)

    def _on_palette_swatch_double_click(self, index: int) -> None:
        if self._palette_single_click_after_id is not None:
            self.root.after_cancel(self._palette_single_click_after_id)
            self._palette_single_click_after_id = None
        self._choose_palette_colour(index)

    def _on_use_palette_sequence_changed(self) -> None:
        if self.editor.set_use_palette_sequence(self.use_palette_sequence.get()).changed:
            self._document_changed()

    def _select_palette_colour(self, index: int) -> None:
        self.active_colour.set(index)
        self._rebuild_palette_buttons()

        if hasattr(self, "canvas"):
            self.canvas.redraw()

    def _make_palette_select_command(self, index: int) -> Callable[[], None]:
        def command() -> None:
            self._select_palette_colour(index)

        return command

    def _make_palette_edit_command(self, index: int) -> Callable[[], None]:
        def command() -> None:
            self._choose_palette_colour(index)

        return command

    def _on_palette_selected(self) -> None:
        self._rebuild_palette_buttons()
        if hasattr(self, "canvas"):
            self.canvas.redraw(
            )

    def _build_symmetry_controls(self, parent: ttk.Frame) -> None:
        """Build the symmetry controls in the sidebar,
        allowing the user to select symmetry operations for the pattern."""
        frame = ttk.LabelFrame(parent, text="Symmetri i repeterende enhet", padding=8)
        frame.pack(fill=tk.X, pady=(0, 8))
        operations = [
            ("identity", "Original"),
            ("mirror_x", "Speil vertikalt"),
            ("mirror_y", "Speil horisontalt"),
            ("rotate_180", "Roter 180°"),
            ("rotate_90", "Roter 90°"),
            ("rotate_270", "Roter 270°"),
            ("diag_main", "Hoveddiagonal"),
            ("diag_anti", "Motdiagonal"),
        ]
        for row, (operation, label) in enumerate(operations):
            variable = tk.BooleanVar(value=operation == "identity")
            self.symmetry_vars[operation] = variable
            ttk.Checkbutton(frame, text=label, variable=variable, command=self._apply_symmetry).grid(
                row=row, column=0, sticky=tk.W
            )

    def _apply_controls(self) -> None:
        try:
            result = self.editor.set_grid(
                unit_width=self.unit_width.get(),
                unit_height=self.unit_height.get(),
                repeats_x=self.repeats_x.get(),
                repeats_y=self.repeats_y.get(),
                repeat_left_column=self.repeat_left_column.get(),
                repeat_right_column=self.repeat_right_column.get(),
                repeat_top_row=self.repeat_top_row.get(),
                repeat_bottom_row=self.repeat_bottom_row.get(),
            )
        except (tk.TclError, ValueError) as error:
            messagebox.showerror("Ugyldige innstillinger", str(error))
            return
        if result.changed:
            # Square-only symmetry is switched off quietly when the unit stops being square.
            self._sync_symmetry_vars()
            self._document_changed()

    def _resize_grid_axis(self, axis: Axis, index: int, *, insertion: bool) -> None:
        """Insert or remove a row/column; the symmetry may add or remove more."""
        if not insertion and not can_remove_grid_line(self.document, axis, index):
            messagebox.showinfo("Kan ikke fjerne", "Rutenettet må ha minst én rad og én kolonne.")
            return
        self.editor.change_grid_line(axis, index, insertion=insertion)
        self.unit_width.set(self.document.unit_width)
        self.unit_height.set(self.document.unit_height)
        self._sync_symmetry_vars()
        self._document_changed()

    def _insert_column_at(self, index: int) -> None:
        self._resize_grid_axis("column", index, insertion=True)

    def _remove_column_at(self, index: int) -> None:
        self._resize_grid_axis("column", index, insertion=False)

    def _insert_row_at(self, index: int) -> None:
        self._resize_grid_axis("row", index, insertion=True)

    def _remove_row_at(self, index: int) -> None:
        self._resize_grid_axis("row", index, insertion=False)

    def _open_resize_grid_dialog(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Legg til eller fjern rad/kolonne")
        dialog.transient(self.root)
        dialog.resizable(False, False)

        body = ttk.Frame(dialog, padding=12)
        body.grid(row=0, column=0, sticky=tk.NSEW)
        action_var = tk.StringVar(value="Legg til")
        target_var = tk.StringVar(value="Øverste rad")
        number_var = tk.IntVar(value=1)
        places: dict[str, GridPlace] = {
            "Øverste rad": "top_row",
            "Nederste rad": "bottom_row",
            "Første kolonne": "first_column",
            "Siste kolonne": "last_column",
            "Rad med nummer": "row",
            "Kolonne med nummer": "column",
        }
        targets = tuple(places)

        ttk.Label(body, text="Handling").grid(row=0, column=0, sticky=tk.W, pady=3)
        action_combo = ttk.Combobox(
            body, textvariable=action_var, values=("Legg til", "Fjern"), state="readonly", width=22
        )
        action_combo.grid(row=0, column=1, sticky=tk.EW, padx=(8, 0), pady=3)
        ttk.Label(body, text="Plassering").grid(row=1, column=0, sticky=tk.W, pady=3)
        target_combo = ttk.Combobox(body, textvariable=target_var, values=targets, state="readonly", width=22)
        target_combo.grid(row=1, column=1, sticky=tk.EW, padx=(8, 0), pady=3)
        number_label = ttk.Label(body, text="Nummer")
        number_label.grid(row=2, column=0, sticky=tk.W, pady=3)
        number_spin = ttk.Spinbox(body, from_=1, to=100, textvariable=number_var, width=8)
        number_spin.grid(row=2, column=1, sticky=tk.W, padx=(8, 0), pady=3)
        note = ttk.Label(
            body,
            text="Aktiv symmetri kan legge til eller fjerne flere rader/kolonner.",
            wraplength=330,
        )
        note.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(8, 2))
        buttons = ttk.Frame(body)
        buttons.grid(row=4, column=0, columnspan=2, sticky=tk.E, pady=(10, 0))

        def refresh_number_control(*_args: object) -> None:
            numbered = target_var.get() in {"Rad med nummer", "Kolonne med nummer"}
            state = "normal" if numbered else "disabled"
            number_spin.configure(state=state)
            number_label.configure(state=state)
            is_row = target_var.get() == "Rad med nummer"
            limit = max_line_number(
                self.document, "row" if is_row else "column", insertion=action_var.get() == "Legg til"
            )
            number_spin.configure(to=max(1, limit))
            try:
                if number_var.get() > limit:
                    number_var.set(limit)
            except tk.TclError:
                number_var.set(1)

        def apply_resize() -> None:
            insertion = action_var.get() == "Legg til"
            place = places[target_var.get()]
            number = 1
            if place in {"row", "column"}:
                try:
                    number = int(number_var.get())
                except (tk.TclError, ValueError):
                    messagebox.showerror(
                        "Ugyldig nummer", "Skriv inn et gyldig rad- eller kolonnenummer.", parent=dialog
                    )
                    return
            axis, index = grid_line_for_place(self.document, place, insertion=insertion, number=number)
            self._resize_grid_axis(axis, index, insertion=insertion)
            dialog.destroy()

        ttk.Button(buttons, text="Utfør", command=apply_resize).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(buttons, text="Avbryt", command=dialog.destroy).pack(side=tk.LEFT)
        target_var.trace_add("write", refresh_number_control)
        action_var.trace_add("write", refresh_number_control)
        refresh_number_control()
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.update_idletasks()
        dialog.wait_visibility()
        dialog.grab_set()
        dialog.wait_window()

    def _sync_symmetry_vars(self) -> None:
        for name, variable in self.symmetry_vars.items():
            variable.set(name in self.document.symmetry)

    def _apply_symmetry(self) -> None:
        operations = [name for name, variable in self.symmetry_vars.items() if variable.get()]
        result = self.editor.set_symmetry(operations)
        self._sync_symmetry_vars()
        if result.removed_symmetry:
            messagebox.showinfo("Kvadratisk enhet kreves", "Kvartrotasjon og diagonal symmetri krever kvadratisk enhet.")
        if hasattr(self, "canvas"):
            self._document_changed()

    def _choose_palette_colour(self, index: int) -> None:
        current_sequence = list(self.document.palette_sequences[index])
        selected_sequence = self._open_palette_sequence_dialog(index, current_sequence)
        if selected_sequence is None:
            return
        if selected_sequence == current_sequence:
            return

        self.editor.set_colour_sequence(index, selected_sequence)
        self._rebuild_palette_buttons()
        self._document_changed()

    def _open_palette_sequence_dialog(self, index: int, initial_sequence: list[str]) -> list[str] | None:
        sequence = list(initial_sequence) if initial_sequence else [self.document.palette[index]]

        dialog = tk.Toplevel(self.root)
        dialog.title("Velg palettfarge")
        dialog.transient(self.root)
        dialog.resizable(False, False)

        body = ttk.Frame(dialog, padding=10)
        body.grid(row=0, column=0, sticky=tk.NSEW)

        preview_label = ttk.Label(body, text="Nåværende sekvens")
        preview_label.grid(row=0, column=0, columnspan=3, sticky=tk.W)

        preview = tk.Canvas(body, width=260, height=24, highlightthickness=1, highlightbackground="#666666")
        preview.grid(row=1, column=0, columnspan=3, sticky=tk.EW, pady=(4, 10))

        count_var = tk.IntVar(value=max(1, len(sequence)))
        part_var = tk.StringVar(value="1")
        current_part_colour = tk.StringVar(value=sequence[0])

        ttk.Label(body, text="Antall farger").grid(row=2, column=0, sticky=tk.W)
        count_spin = ttk.Spinbox(body, from_=1, to=MAX_SEQUENCE_LENGTH, textvariable=count_var, width=8)
        count_spin.grid(row=2, column=1, sticky=tk.W, padx=(6, 0))

        ttk.Label(body, text="Del i sekvens").grid(row=3, column=0, sticky=tk.W, pady=(8, 0))
        part_combo = ttk.Combobox(body, textvariable=part_var, state="readonly", width=8)
        part_combo.grid(row=3, column=1, sticky=tk.W, padx=(6, 0), pady=(8, 0))

        ttk.Label(body, text="Valgt del").grid(row=4, column=0, sticky=tk.W, pady=(8, 0))
        selected_part_swatch = tk.Canvas(body, width=44, height=20, highlightthickness=1, highlightbackground="#666666")
        selected_part_swatch.grid(row=4, column=1, sticky=tk.W, padx=(6, 0), pady=(8, 0))

        button_row = ttk.Frame(body)
        button_row.grid(row=5, column=0, columnspan=3, sticky=tk.EW, pady=(10, 0))
        ttk.Button(button_row, text="Velg farge for del", command=lambda: choose_part_colour()).pack(side=tk.LEFT)

        action_row = ttk.Frame(body)
        action_row.grid(row=6, column=0, columnspan=3, sticky=tk.E, pady=(12, 0))

        result: list[str] | None = None

        def draw_preview() -> None:
            preview.delete("all")
            width = 260
            height = 24
            segment_width = max(1, width // len(sequence))
            for segment_index, colour in enumerate(sequence):
                left = segment_index * segment_width
                right = width if segment_index == len(sequence) - 1 else (segment_index + 1) * segment_width
                preview.create_rectangle(left, 0, right, height, fill=colour, outline=colour)
                preview.create_text(
                    (left + right) / 2,
                    height / 2,
                    text=str(segment_index + 1),
                    fill="white",
                )

        def redraw_selected_part() -> None:
            selected_part_swatch.delete("all")
            colour = sequence[int(part_var.get()) - 1]
            current_part_colour.set(colour)
            selected_part_swatch.create_rectangle(0, 0, 44, 20, fill=colour, outline=colour)

        def refresh_part_options() -> None:
            options = [str(value) for value in range(1, len(sequence) + 1)]
            part_combo["values"] = options
            if part_var.get() not in options:
                part_var.set(options[0])
            redraw_selected_part()

        def apply_count_change(*_args: object) -> None:
            try:
                target = max(1, int(count_var.get()))
            except (tk.TclError, ValueError):
                return
            sequence[:] = resize_sequence(sequence, target)
            refresh_part_options()
            draw_preview()

        def choose_part_colour() -> None:
            part_index = int(part_var.get()) - 1
            selected = ask_rgb_colour(
                dialog,
                sequence[part_index],
                title=f"Velg farge for del {part_index + 1}",
            )
            if selected:
                sequence[part_index] = selected
                redraw_selected_part()
                draw_preview()

        def on_ok() -> None:
            nonlocal result
            result = list(sequence)
            dialog.destroy()

        def on_cancel() -> None:
            dialog.destroy()

        ttk.Button(action_row, text="OK", command=on_ok).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(action_row, text="Avbryt", command=on_cancel).pack(side=tk.LEFT)

        count_var.trace_add("write", apply_count_change)
        part_var.trace_add("write", lambda *_args: redraw_selected_part())

        refresh_part_options()
        draw_preview()
        dialog.update_idletasks()
        try:
            dialog.wait_visibility()
            dialog.grab_set()
        except tk.TclError:
            # Some window managers can reject grab during early mapping.
            pass
        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        dialog.wait_window()

        return result

    def _add_palette_colour(self) -> None:
        selected = ask_rgb_colour(self.root, "#808080", title="Legg til palettfarge")
        if selected:
            self._append_palette_colour(selected)

    def _add_dmc_palette_colour(self) -> None:
        selected = ask_dmc_colour(self.root, title="Legg til DMC-farge")
        if selected:
            self._append_palette_colour(selected)

    def _append_palette_colour(self, colour: str) -> None:
        self.editor.add_colour(colour)
        self._rebuild_palette_buttons()
        self._document_changed()

    def _change_mode(self) -> None:
        self.canvas.set_mode(self.mode.get())

    def _change_stitch_tool(self) -> None:
        self.mode.set("edit")
        self.canvas.set_mode("edit")
        self.canvas.set_stitch_tool(self.stitch_tool.get())

    def _update_undo_redo_controls(self) -> None:
        if not hasattr(self, "edit_menu"):
            return
        self.edit_menu.entryconfigure("Angre", state=tk.NORMAL if self.editor.can_undo else tk.DISABLED)
        self.edit_menu.entryconfigure("Gjør om", state=tk.NORMAL if self.editor.can_redo else tk.DISABLED)

    def _restore_history_state(self, status: str) -> None:
        self._sync_controls_from_document()
        self.canvas.redraw()
        self.status.set(status)
        self._update_undo_redo_controls()

    def undo(self) -> None:
        if self.editor.undo():
            self._restore_history_state("Angret siste endring")

    def redo(self) -> None:
        if self.editor.redo():
            self._restore_history_state("Gjorde om siste endring")

    @staticmethod
    def _run_history_shortcut(action: Callable[[], None]) -> str:
        action()
        return "break"

    def _document_changed(self) -> None:
        self.canvas.redraw()
        self.status.set("Endret")
        self._update_undo_redo_controls()

    def _sync_controls_from_document(self) -> None:
        self.unit_width.set(self.document.unit_width)
        self.unit_height.set(self.document.unit_height)
        self.repeats_x.set(self.document.repeats_x)
        self.repeats_y.set(self.document.repeats_y)
        self.repeat_left_column.set(self.document.repeat_left_column)
        self.repeat_right_column.set(self.document.repeat_right_column)
        self.repeat_top_row.set(self.document.repeat_top_row)
        self.repeat_bottom_row.set(self.document.repeat_bottom_row)
        self.use_palette_sequence.set(self.document.use_palette_sequence)
        self._sync_override_controls()
        if hasattr(self, "canvas"):
            self.canvas.set_edit_target(self._selected_target())
        self._sync_symmetry_vars()
        self.active_colour.set(0)
        self._rebuild_palette_buttons()

    def new_document(self) -> None:
        self.editor.load(PatternDocument())
        self.current_path = None
        self._update_undo_redo_controls()
        self._sync_controls_from_document()
        self.canvas.redraw()
        self.status.set("Nytt dokument")

    def open_document(self) -> None:
        filename = filedialog.askopenfilename(filetypes=[("Mønsterfiler", "*.json"), ("Alle filer", "*")])
        if not filename:
            return
        self._open_document_from_path(Path(filename))

    def _open_document_from_path(self, path: Path) -> None:
        try:
            self._load_document_path(path)
        except (OSError, ValueError) as error:
            messagebox.showerror("Kunne ikke åpne mønster", str(error))

    def _load_document_path(self, path: Path) -> None:
        self.editor.load(load_document(path))
        self.current_path = path
        self._update_undo_redo_controls()
        self._sync_controls_from_document()
        self.canvas.redraw()
        self.status.set(f"Åpnet {self.current_path.name}")

    def save_document(self) -> None:
        if self.current_path is None:
            self.save_document_as()
            return
        try:
            save_document(self.document, self.current_path)
            self.status.set(f"Lagret {self.current_path.name}")
        except OSError as error:
            messagebox.showerror("Kunne ikke lagre mønster", str(error))

    def save_document_as(self) -> None:
        filename = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("Monsterfiler", "*.json")]
        )
        if not filename:
            return
        self.current_path = Path(filename)
        self.save_document()

    def export_png(self) -> None:
        filename = filedialog.asksaveasfilename(
            defaultextension=".png", filetypes=[("PNG-bilde", "*.png")]
        )
        if not filename:
            return
        try:
            image = render_image(self.document, cell_size=18, draw_grid=True)
            image.save(filename)
            self.status.set(f"Eksporterte {Path(filename).name}")
        except (OSError, ValueError) as error:
            messagebox.showerror("Kunne ikke eksportere bilde", str(error))
