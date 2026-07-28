from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

from kvale.core.model import ColourRule, PatternDocument
from kvale.core.renderer import render_image
from kvale.core.serialization import load_document, save_document
from kvale.gui.canvas import PatternCanvas


class KvaleApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Kvale")
        self.root.geometry("1180x760")
        self.document = PatternDocument()
        self.current_path: Path | None = None
        self.active_colour = tk.IntVar(value=0)
        self.mode = tk.StringVar(value="edit")
        self.status = tk.StringVar(value="Klar")
        self.symmetry_vars: dict[str, tk.BooleanVar] = {}
        self.palette_buttons: list[ttk.Button] = []
        self._build_ui()
        self._sync_controls_from_document()
        self.canvas.redraw()

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
        self._build_colour_rule_controls(sidebar)

        toolbar = ttk.Frame(workspace)
        toolbar.pack(fill=tk.X, pady=(0, 6))
        ttk.Radiobutton(
            toolbar, text="Rediger repeterende enhet", variable=self.mode, value="edit", command=self._change_mode
        ).pack(side=tk.LEFT)
        ttk.Radiobutton(
            toolbar, text="Se repetisjoner", variable=self.mode, value="preview", command=self._change_mode
        ).pack(side=tk.LEFT, padx=12)
        ttk.Label(toolbar, text="Venstreklikk: sett farge; høyreklikk: slett").pack(side=tk.RIGHT)

        self.canvas = PatternCanvas(
            workspace,
            document_getter=lambda: self.document,
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
        self.root.config(menu=menu)
        self.root.bind("<Control-n>", lambda _event: self.new_document())
        self.root.bind("<Control-o>", lambda _event: self.open_document())
        self.root.bind("<Control-s>", lambda _event: self.save_document())

    def _spin_row(self, parent: ttk.Frame, label: str, variable: tk.IntVar, row: int) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Spinbox(parent, from_=1, to=100, textvariable=variable, width=7, command=self._apply_controls).grid(
            row=row, column=1, sticky=tk.E, pady=2
        )

    def _build_document_controls(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Rutenett og repetisjoner", padding=8)
        frame.pack(fill=tk.X, pady=(0, 8))
        self.unit_width = tk.IntVar(value=12)
        self.unit_height = tk.IntVar(value=12)
        self.repeats_x = tk.IntVar(value=6)
        self.repeats_y = tk.IntVar(value=2)
        self._spin_row(frame, "Bredde repeterende enhet", self.unit_width, 0)
        self._spin_row(frame, "Høyde repeterende enhet", self.unit_height, 1)
        self._spin_row(frame, "Repetisjoner horisontalt", self.repeats_x, 2)
        self._spin_row(frame, "Repetisjoner vertikalt", self.repeats_y, 3)
        ttk.Button(frame, text="Bruk", command=self._apply_controls).grid(
            row=4, column=0, columnspan=2, sticky=tk.EW, pady=(6, 0)
        )

    def _build_palette_controls(self, parent: ttk.Frame) -> None:
        self.palette_frame = ttk.LabelFrame(parent, text="Farger", padding=8)
        self.palette_frame.pack(fill=tk.X, pady=(0, 8))
        self._rebuild_palette_buttons()

    def _rebuild_palette_buttons(self) -> None:
        for child in self.palette_frame.winfo_children():
            child.destroy()
        for index, colour in enumerate(self.document.palette):
            button = tk.Radiobutton(
                self.palette_frame,
                text=f"Farge {index + 1}",
                variable=self.active_colour,
                value=index,
                indicatoron=False,
                background=colour,
                activebackground=colour,
                width=10,
                command=self.canvas.redraw if hasattr(self, "canvas") else None,
            )
            button.grid(row=index // 2, column=index % 2, sticky=tk.EW, padx=2, pady=2)
            button.bind("<Double-Button-1>", lambda _event, i=index: self._choose_palette_colour(i))
        ttk.Button(self.palette_frame, text="Legg til farge", command=self._add_palette_colour).grid(
            row=(len(self.document.palette) + 1) // 2, column=0, columnspan=2, sticky=tk.EW, pady=(6, 0)
        )

    def _build_symmetry_controls(self, parent: ttk.Frame) -> None:
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

    def _build_colour_rule_controls(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Uavhengig fargerepetisjon", padding=8)
        frame.pack(fill=tk.X, pady=(0, 8))
        self.colour_mode = tk.StringVar(value="fixed")
        self.colour_sequence = tk.StringVar(value="0,1,2,1,3")
        self.colour_advance = tk.StringVar(value="unit_x")
        ttk.Label(frame, text="Modus").grid(row=0, column=0, sticky=tk.W)
        ttk.Combobox(
            frame,
            textvariable=self.colour_mode,
            values=("fixed", "unit_cycle", "cell_cycle", "sequence"),
            state="readonly",
            width=12,
        ).grid(row=0, column=1, sticky=tk.EW)
        ttk.Label(frame, text="Sekvens").grid(row=1, column=0, sticky=tk.W)
        ttk.Entry(frame, textvariable=self.colour_sequence, width=14).grid(row=1, column=1, sticky=tk.EW)
        ttk.Label(frame, text="Advance by").grid(row=2, column=0, sticky=tk.W)
        ttk.Combobox(
            frame,
            textvariable=self.colour_advance,
            values=("unit_x", "unit_y", "unit_xy", "cell_x", "cell_y"),
            state="readonly",
            width=12,
        ).grid(row=2, column=1, sticky=tk.EW)
        ttk.Button(frame, text="Bruk fargeregel", command=self._apply_colour_rule).grid(
            row=3, column=0, columnspan=2, sticky=tk.EW, pady=(6, 0)
        )

    def _apply_controls(self) -> None:
        try:
            new_width = max(1, self.unit_width.get())
            new_height = max(1, self.unit_height.get())
            self.document.unit_width = new_width
            self.document.unit_height = new_height
            self.document.repeats_x = max(1, self.repeats_x.get())
            self.document.repeats_y = max(1, self.repeats_y.get())
            self.document.motif = [
                mark for mark in self.document.motif if mark.x < new_width and mark.y < new_height
            ]
            self._apply_symmetry(show_errors=False)
            self._document_changed()
        except (tk.TclError, ValueError) as error:
            messagebox.showerror("Ugyldige innstillinger", str(error))

    def _apply_symmetry(self, show_errors: bool = True) -> None:
        operations = [name for name, variable in self.symmetry_vars.items() if variable.get()]
        if "identity" not in operations:
            operations.insert(0, "identity")
            self.symmetry_vars["identity"].set(True)
        square_only = {"rotate_90", "rotate_270", "diag_main", "diag_anti"}
        if self.document.unit_width != self.document.unit_height:
            selected = square_only.intersection(operations)
            if selected:
                for operation in selected:
                    self.symmetry_vars[operation].set(False)
                    operations.remove(operation)
                if show_errors:
                    messagebox.showinfo("Kvadratisk enhet kreves", "Kvartrotasjon og diagonal symmetri krever kvadratisk enhet.")
        self.document.symmetry = operations
        if hasattr(self, "canvas"):
            self._document_changed()

    def _apply_colour_rule(self) -> None:
        try:
            sequence = [int(part.strip()) for part in self.colour_sequence.get().split(",") if part.strip()]
            if not sequence:
                sequence = [0]
            self.document.colour_rule = ColourRule(
                mode=self.colour_mode.get(),
                sequence=sequence,
                advance=self.colour_advance.get(),
            )
            self._document_changed()
        except ValueError as error:
            messagebox.showerror("Ugyldig fargeregel", str(error))

    def _choose_palette_colour(self, index: int) -> None:
        selected = colorchooser.askcolor(color=self.document.palette[index], title="Velg palettfarge")[1]
        if selected:
            self.document.palette[index] = selected
            self._rebuild_palette_buttons()
            self._document_changed()

    def _add_palette_colour(self) -> None:
        selected = colorchooser.askcolor(color="#808080", title="Legg til palettfarge")[1]
        if selected:
            self.document.palette.append(selected)
            self._rebuild_palette_buttons()
            self._document_changed()

    def _change_mode(self) -> None:
        self.canvas.set_mode(self.mode.get())

    def _document_changed(self) -> None:
        self.canvas.redraw()
        self.status.set("Endret")

    def _sync_controls_from_document(self) -> None:
        self.unit_width.set(self.document.unit_width)
        self.unit_height.set(self.document.unit_height)
        self.repeats_x.set(self.document.repeats_x)
        self.repeats_y.set(self.document.repeats_y)
        for name, variable in self.symmetry_vars.items():
            variable.set(name in self.document.symmetry)
        self.colour_mode.set(self.document.colour_rule.mode)
        self.colour_sequence.set(",".join(str(value) for value in self.document.colour_rule.sequence))
        self.colour_advance.set(self.document.colour_rule.advance)
        self.active_colour.set(0)
        self._rebuild_palette_buttons()

    def new_document(self) -> None:
        self.document = PatternDocument()
        self.current_path = None
        self._sync_controls_from_document()
        self.canvas.redraw()
        self.status.set("Nytt dokument")

    def open_document(self) -> None:
        filename = filedialog.askopenfilename(filetypes=[("Mønsterfiler", "*.json"), ("Alle filer", "*")])
        if not filename:
            return
        try:
            self.document = load_document(Path(filename))
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
