from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import font as tkfont
from tkinter import messagebox, ttk

from kvale.gui.dmc_palette import ask_dmc_colour


def rgb_to_hex(red: int, green: int, blue: int) -> str:
    return f"#{red:02x}{green:02x}{blue:02x}"


def hex_to_rgb(colour: str) -> tuple[int, int, int]:
    value = colour.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(character * 2 for character in value)
    if len(value) != 6:
        raise ValueError("Fargen må skrives som #RRGGBB eller #RGB.")
    try:
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
    except ValueError as error:
        raise ValueError("Fargekoden kan bare inneholde heksadesimale tegn.") from error


def ask_rgb_colour(
    parent: tk.Misc,
    initial_colour: str,
    *,
    title: str = "Velg farge",
) -> str | None:
    """Open a consistent RGB/hex colour dialog and return #rrggbb or None."""
    try:
        initial_rgb = hex_to_rgb(initial_colour)
    except ValueError:
        initial_rgb = (128, 128, 128)

    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.transient(parent.winfo_toplevel())
    dialog.resizable(False, False)
    result: str | None = None
    updating = False

    body = ttk.Frame(dialog, padding=12)
    body.grid(row=0, column=0, sticky=tk.NSEW)
    red_var = tk.IntVar(value=initial_rgb[0])
    green_var = tk.IntVar(value=initial_rgb[1])
    blue_var = tk.IntVar(value=initial_rgb[2])
    hex_var = tk.StringVar(value=rgb_to_hex(*initial_rgb))

    preview = tk.Canvas(
        body,
        width=280,
        height=54,
        highlightthickness=1,
        highlightbackground="#666666",
    )
    preview.grid(row=0, column=0, columnspan=3, sticky=tk.EW, pady=(0, 12))

    scales: list[tk.Scale] = []

    def current_rgb() -> tuple[int, int, int]:
        return red_var.get(), green_var.get(), blue_var.get()

    def redraw_preview() -> None:
        colour = rgb_to_hex(*current_rgb())
        preview.delete("all")
        preview.create_rectangle(0, 0, 280, 54, fill=colour, outline=colour)
        preview.create_text(
            140,
            27,
            text=colour.upper(),
            fill=PaletteButton._contrasting_text_colour(colour),
            font=("TkDefaultFont", 10, "bold"),
        )

    def update_from_rgb(*_args: object) -> None:
        nonlocal updating
        if updating:
            return
        try:
            red, green, blue = current_rgb()
        except tk.TclError:
            return
        if not all(0 <= component <= 255 for component in (red, green, blue)):
            return
        updating = True
        hex_var.set(rgb_to_hex(red, green, blue))
        updating = False
        redraw_preview()

    def apply_hex(*_args: object) -> None:
        nonlocal updating
        try:
            red, green, blue = hex_to_rgb(hex_var.get())
        except ValueError as error:
            messagebox.showerror("Ugyldig fargekode", str(error), parent=dialog)
            return
        updating = True
        red_var.set(red)
        green_var.set(green)
        blue_var.set(blue)
        hex_var.set(rgb_to_hex(red, green, blue))
        updating = False
        redraw_preview()

    channel_rows = (
        ("Rød", red_var, "#d95c5c"),
        ("Grønn", green_var, "#54a96b"),
        ("Blå", blue_var, "#5b78d1"),
    )
    for row, (label, variable, trough_colour) in enumerate(channel_rows, start=1):
        ttk.Label(body, text=label).grid(row=row, column=0, sticky=tk.W, padx=(0, 8))
        scale = tk.Scale(
            body,
            from_=0,
            to=255,
            orient=tk.HORIZONTAL,
            variable=variable,
            command=lambda _value: update_from_rgb(),
            showvalue=False,
            length=210,
            resolution=1,
            troughcolor=trough_colour,
            highlightthickness=0,
        )
        scale.grid(row=row, column=1, sticky=tk.EW)
        ttk.Spinbox(
            body,
            from_=0,
            to=255,
            textvariable=variable,
            width=5,
            command=update_from_rgb,
        ).grid(row=row, column=2, sticky=tk.E, padx=(8, 0))
        variable.trace_add("write", update_from_rgb)
        scales.append(scale)

    ttk.Label(body, text="Hex").grid(row=4, column=0, sticky=tk.W, pady=(10, 0))
    hex_entry = ttk.Entry(body, textvariable=hex_var, width=12)
    hex_entry.grid(row=4, column=1, sticky=tk.W, pady=(10, 0))
    ttk.Button(body, text="Bruk kode", command=apply_hex).grid(
        row=4, column=2, sticky=tk.E, padx=(8, 0), pady=(10, 0)
    )
    hex_entry.bind("<Return>", apply_hex)

    def choose_dmc() -> None:
        selected = ask_dmc_colour(dialog, rgb_to_hex(*current_rgb()))
        if selected is None:
            return
        red, green, blue = hex_to_rgb(selected)
        red_var.set(red)
        green_var.set(green)
        blue_var.set(blue)
        hex_var.set(selected)
        redraw_preview()

    ttk.Button(body, text="Velg fra DMC-palett…", command=choose_dmc).grid(
        row=5, column=0, columnspan=3, sticky=tk.EW, pady=(12, 0)
    )

    actions = ttk.Frame(body)
    actions.grid(row=6, column=0, columnspan=3, sticky=tk.E, pady=(14, 0))

    def accept() -> None:
        nonlocal result
        try:
            result = rgb_to_hex(*current_rgb())
        except tk.TclError:
            return
        dialog.destroy()

    ttk.Button(actions, text="OK", command=accept).pack(side=tk.LEFT, padx=(0, 6))
    ttk.Button(actions, text="Avbryt", command=dialog.destroy).pack(side=tk.LEFT)
    dialog.bind("<Escape>", lambda _event: dialog.destroy())
    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
    redraw_preview()
    dialog.update_idletasks()
    try:
        dialog.wait_visibility()
        dialog.grab_set()
    except tk.TclError:
        pass
    dialog.wait_window()
    return result


class PaletteButton(tk.Canvas):
    """Fixed-size palette selector drawn on a Canvas."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        colour: str,
        colours: list[str] | None = None,
        text: str,
        selected: bool,
        command: Callable[[], None],
        edit_command: Callable[[], None] | None = None,
        width: int = 120,
        height: int = 40,
    ) -> None:
        super().__init__(
            master,
            width=width,
            height=height,
            highlightthickness=0,
            borderwidth=0,
            cursor="hand2",
        )

        self.colour = colour
        self.colours = list(colours) if colours else [colour]
        self.label_text = text
        self.selected = selected
        self.command = command
        self.edit_command = edit_command
        self.button_width = width
        self.button_height = height

        self.normal_font = tkfont.nametofont("TkDefaultFont").copy()
        self.selected_font = tkfont.nametofont("TkDefaultFont").copy()
        self.selected_font.configure(weight="bold", slant="italic")
        self._single_click_after_id: str | None = None

        self.bind("<Button-1>", self._on_click)
        self.bind("<Double-Button-1>", self._on_double_click)

        self.redraw()

    def redraw(self) -> None:
        self.delete("all")

        background = self.winfo_toplevel().cget("background")
        self.configure(background=background)

        outer_margin = 2
        outline_gap = 3
        outline_width = 1

        if self.selected:
            self.create_rectangle(
                outer_margin,
                outer_margin,
                self.button_width - outer_margin,
                self.button_height - outer_margin,
                outline=self.colour,
                width=outline_width,
            )

        box_left = outer_margin + outline_gap
        box_top = outer_margin + outline_gap
        box_right = self.button_width - outer_margin - outline_gap
        box_bottom = self.button_height - outer_margin - outline_gap

        segment_width = (box_right - box_left) / len(self.colours)
        for index, colour in enumerate(self.colours):
            left = box_left + index * segment_width
            right = box_right if index == len(self.colours) - 1 else box_left + (index + 1) * segment_width
            self.create_rectangle(left, box_top, right, box_bottom, fill=colour, outline=colour)

        self.create_text(
            self.button_width / 2,
            self.button_height / 2,
            text=self.label_text,
            font=self.selected_font if self.selected else self.normal_font,
            fill=self._contrasting_text_colour(self.colours[len(self.colours) // 2]),
        )

    def set_selected(self, selected: bool) -> None:
        self.selected = selected
        self.redraw()

    def set_colour(self, colour: str) -> None:
        self.colour = colour
        self.colours = [colour]
        self.redraw()

    def set_colours(self, colours: list[str]) -> None:
        self.colours = list(colours) if colours else [self.colour]
        self.colour = self.colours[0]
        self.redraw()

    def _on_click(self, _event: tk.Event[tk.Misc]) -> None:
        # Defer single-click so a double-click can cancel it.
        self._single_click_after_id = self.after(220, self._run_single_click)

    def _on_double_click(self, _event: tk.Event[tk.Misc]) -> None:
        if self._single_click_after_id is not None:
            self.after_cancel(self._single_click_after_id)
            self._single_click_after_id = None
        if self.edit_command is not None:
            self.edit_command()

    def _run_single_click(self) -> None:
        self._single_click_after_id = None
        self.command()

    @staticmethod
    def _contrasting_text_colour(colour: str) -> str:
        """Return black or white depending on the background brightness."""

        value = colour.lstrip("#")

        if len(value) != 6:
            return "black"

        try:
            red = int(value[0:2], 16)
            green = int(value[2:4], 16)
            blue = int(value[4:6], 16)
        except ValueError:
            return "black"

        brightness = (
            red * 299
            + green * 587
            + blue * 114
        ) / 1000

        return "black" if brightness > 140 else "white"
