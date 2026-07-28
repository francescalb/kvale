from collections.abc import Callable
import tkinter as tk
from tkinter import font as tkfont


class PaletteButton(tk.Canvas):
    """Fixed-size palette selector drawn on a Canvas."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        colour: str,
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

        self.create_rectangle(
            box_left,
            box_top,
            box_right,
            box_bottom,
            fill=self.colour,
            outline=self.colour,
        )

        self.create_text(
            self.button_width / 2,
            self.button_height / 2,
            text=self.label_text,
            font=self.selected_font if self.selected else self.normal_font,
            fill=self._contrasting_text_colour(self.colour),
        )

    def set_selected(self, selected: bool) -> None:
        self.selected = selected
        self.redraw()

    def set_colour(self, colour: str) -> None:
        self.colour = colour
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