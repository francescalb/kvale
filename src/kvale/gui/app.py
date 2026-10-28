from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

from kvale.core.editing import MAX_SEQUENCE_LENGTH, resize_sequence
from kvale.core.editor import Editor, EditResult
from kvale.core.model import PatternDocument
from kvale.core.renderer import render_image
from kvale.core.serialization import load_document, save_document
from kvale.gui.canvas import PatternCanvas


class KvaleApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Kvale")
        self.root.geometry("1180x760")
        self.editor = Editor()
        self.current_path: Path | None = None
        self.active_colour = tk.IntVar(value=0)
        self.mode = tk.StringVar(value="edit")
        self.status = tk.StringVar(value="Klar")
        self.symmetry_vars: dict[str, tk.BooleanVar] = {}
        self.palette_buttons: list[tk.Canvas] = []
        self._palette_single_click_after_id: str | None = None
        self._build_ui()
        self._sync_controls_from_document()
        self.canvas.redraw()

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

        sidebar = ttk.Frame(main, padding=10)
        workspace = ttk.Frame(main, padding=8)
        main.add(sidebar, weight=0)
        main.add(workspace, weight=1)

        self._build_document_controls(sidebar)
        self._build_palette_controls(sidebar)
        self._build_symmetry_controls(sidebar)

        toolbar = ttk.Frame(workspace)
        toolbar.pack(fill=tk.X, pady=(0, 6))
        ttk.Radiobutton(
            toolbar, text="Rediger repeterende enhet", variable=self.mode, value="edit", command=self._change_mode
        ).pack(side=tk.LEFT)
        ttk.Radiobutton(
            toolbar, text="Se repetisjoner", variable=self.mode, value="preview", command=self._change_mode
        ).pack(side=tk.LEFT, padx=12)
        ttk.Label(
            toolbar,
            text="Venstre: farg/legg til, hoyre: slett.",
        ).pack(side=tk.RIGHT)

        self.canvas = PatternCanvas(
            workspace,
            editor=self.editor,
            active_colour_getter=self.active_colour.get,
            on_change=self._document_changed,
            on_insert_column=self._insert_column_at,
            on_remove_column=self._remove_column_at,
            on_insert_row=self._insert_row_at,
            on_remove_row=self._remove_row_at,
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
        edit_menu = tk.Menu(menu, tearoff=False)
        edit_menu.add_command(label="Angre", command=self.undo, accelerator="Ctrl+Z")
        edit_menu.add_command(label="Gjør om", command=self.redo, accelerator="Ctrl+Y")
        menu.add_cascade(label="Rediger", menu=edit_menu)
        self.root.config(menu=menu)
        self.root.bind("<Control-n>", lambda _event: self.new_document())
        self.root.bind("<Control-o>", lambda _event: self.open_document())
        self.root.bind("<Control-s>", lambda _event: self.save_document())
        self.root.bind("<Control-z>", lambda _event: self.undo())
        self.root.bind("<Control-y>", lambda _event: self.redo())
        self.root.bind("<Control-Z>", lambda _event: self.redo())  # Ctrl+Shift+Z

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

    def _build_palette_controls(self, parent: ttk.Frame) -> None:
        self.palette_frame = ttk.LabelFrame(parent, text="Farger", padding=8)
        self.palette_frame.pack(fill=tk.X, pady=(0, 8))
        self.use_palette_sequence = tk.BooleanVar(value=False)
        self._rebuild_palette_buttons()

    def _rebuild_palette_buttons(self) -> None:
        for child in self.palette_frame.winfo_children():
            child.destroy()

        selected_index = self.active_colour.get()
        self.palette_buttons = []

        for index, sequence in enumerate(self.document.palette_sequences):
            row = index
            is_selected = index == selected_index

            label = ttk.Label(
                self.palette_frame,
                text=f"#{index + 1}",
                font=("TkDefaultFont", 9, "bold") if is_selected else ("TkDefaultFont", 9),
            )
            label.grid(row=row, column=0, sticky=tk.W, padx=(0, 6), pady=2)
            label.bind("<Button-1>", self._make_palette_single_click_handler(index))

            swatch = tk.Canvas(
                self.palette_frame,
                width=120,
                height=18,
                highlightthickness=0,
                borderwidth=0,
                cursor="hand2",
            )
            swatch.grid(row=row, column=1, sticky=tk.W, pady=2)

            segment_width = max(1, 120 // len(sequence))
            for segment_index, segment_colour in enumerate(sequence):
                left = segment_index * segment_width
                right = 120 if segment_index == len(sequence) - 1 else (segment_index + 1) * segment_width
                swatch.create_rectangle(left, 0, right, 18, fill=segment_colour, outline=segment_colour)

            border = 2 if is_selected else 1
            swatch.create_rectangle(
                border // 2,
                border // 2,
                120 - border // 2,
                18 - border // 2,
                outline="#000000",
                width=border,
            )
            swatch.bind("<Button-1>", self._make_palette_single_click_handler(index))
            swatch.bind("<Double-Button-1>", self._make_palette_double_click_handler(index))
            self.palette_buttons.append(swatch)

        ttk.Button(
            self.palette_frame,
            text="Legg til farge",
            command=self._add_palette_colour,
        ).grid(
            row=len(self.document.palette),
            column=0,
            columnspan=2,
            sticky=tk.EW,
            pady=(6, 0),
        )
        ttk.Checkbutton(
            self.palette_frame,
            text="Bruk fargeskvens",
            variable=self.use_palette_sequence,
            command=self._on_use_palette_sequence_changed,
        ).grid(
            row=len(self.document.palette) + 1,
            column=0,
            columnspan=2,
            sticky=tk.W,
            pady=(6, 0),
        )

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
        self.editor.set_use_palette_sequence(self.use_palette_sequence.get())
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
            # Read every control before changing anything, so an invalid entry
            # leaves the document untouched.
            self.editor.set_grid(
                unit_width=self.unit_width.get(),
                unit_height=self.unit_height.get(),
                repeats_x=self.repeats_x.get(),
                repeats_y=self.repeats_y.get(),
                repeat_left_column=self.repeat_left_column.get(),
                repeat_right_column=self.repeat_right_column.get(),
                repeat_top_row=self.repeat_top_row.get(),
                repeat_bottom_row=self.repeat_bottom_row.get(),
            )
            self._sync_symmetry_vars()
            self._document_changed()
        except (tk.TclError, ValueError) as error:
            messagebox.showerror("Ugyldige innstillinger", str(error))

    def _column_count_changed(self, result: EditResult) -> None:
        if result.changed:
            self.unit_width.set(self.document.unit_width)
            self._sync_symmetry_vars()
            self._document_changed()

    def _row_count_changed(self, result: EditResult) -> None:
        if result.changed:
            self.unit_height.set(self.document.unit_height)
            self._sync_symmetry_vars()
            self._document_changed()

    def _insert_column_at(self, index: int) -> None:
        self._column_count_changed(self.editor.insert_column(index))

    def _remove_column_at(self, index: int) -> None:
        self._column_count_changed(self.editor.remove_column(index))

    def _insert_row_at(self, index: int) -> None:
        self._row_count_changed(self.editor.insert_row(index))

    def _remove_row_at(self, index: int) -> None:
        self._row_count_changed(self.editor.remove_row(index))

    def _sync_symmetry_vars(self) -> None:
        for name, variable in self.symmetry_vars.items():
            variable.set(name in self.document.symmetry)

    def _apply_symmetry(self) -> None:
        operations = [name for name, variable in self.symmetry_vars.items() if variable.get()]
        result = self.editor.set_symmetry(operations)
        self._sync_symmetry_vars()
        if result.removed_symmetry:
            messagebox.showinfo("Kvadratisk enhet kreves", "Kvartrotasjon og diagonal symmetri krever kvadratisk enhet.")
        self._document_changed()

    def _choose_palette_colour(self, index: int) -> None:
        current_sequence = list(self.document.palette_sequences[index])
        selected_sequence = self._open_palette_sequence_dialog(index, current_sequence)
        if selected_sequence is None:
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
            selected = colorchooser.askcolor(
                color=sequence[part_index],
                title=f"Velg farge for del {part_index + 1}",
                parent=dialog,
            )[1]
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
        selected = colorchooser.askcolor(color="#808080", title="Legg til palettfarge")[1]
        if selected:
            self.editor.add_colour(selected)
            self._rebuild_palette_buttons()
            self._document_changed()

    def _change_mode(self) -> None:
        self.canvas.set_mode(self.mode.get())

    def _document_changed(self) -> None:
        self.canvas.redraw()
        self.status.set("Endret")

    def _sync_controls_from_document(self, reset_selection: bool = True) -> None:
        self.unit_width.set(self.document.unit_width)
        self.unit_height.set(self.document.unit_height)
        self.repeats_x.set(self.document.repeats_x)
        self.repeats_y.set(self.document.repeats_y)
        self.repeat_left_column.set(self.document.repeat_left_column)
        self.repeat_right_column.set(self.document.repeat_right_column)
        self.repeat_top_row.set(self.document.repeat_top_row)
        self.repeat_bottom_row.set(self.document.repeat_bottom_row)
        self.use_palette_sequence.set(self.document.use_palette_sequence)
        self._sync_symmetry_vars()
        if reset_selection or self.active_colour.get() >= len(self.document.palette_sequences):
            self.active_colour.set(0)
        self._rebuild_palette_buttons()

    def undo(self) -> None:
        if self.editor.undo():
            self._history_changed("Angret")

    def redo(self) -> None:
        if self.editor.redo():
            self._history_changed("Gjort om")

    def _history_changed(self, message: str) -> None:
        self._sync_controls_from_document(reset_selection=False)
        self.canvas.redraw()
        self.status.set(message)

    def new_document(self) -> None:
        self.editor.load(PatternDocument())
        self.current_path = None
        self._sync_controls_from_document()
        self.canvas.redraw()
        self.status.set("Nytt dokument")

    def open_document(self) -> None:
        filename = filedialog.askopenfilename(filetypes=[("Mønsterfiler", "*.json"), ("Alle filer", "*")])
        if not filename:
            return
        try:
            self.editor.load(load_document(Path(filename)))
            self.current_path = Path(filename)
            self._sync_controls_from_document()
            self.canvas.redraw()
            self.status.set(f"Åpnet {self.current_path.name}")
        except (OSError, ValueError) as error:
            messagebox.showerror("Kunne ikke åpne mønster", str(error))

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
