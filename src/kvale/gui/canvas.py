from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

from kvale.core.model import PatternDocument, Mark
from kvale.core.renderer import build_colour_grid
from kvale.core.symmetry import expand_marks


class PatternCanvas(tk.Canvas):
    def __init__(
        self,
        master: tk.Misc,
        document_getter: Callable[[], PatternDocument],
        active_colour_getter: Callable[[], int],
        on_change: Callable[[], None],
    ) -> None:
        super().__init__(master, background="white", highlightthickness=0)
        self.document_getter = document_getter
        self.active_colour_getter = active_colour_getter
        self.on_change = on_change
        self.cell_size = 20
        self.mode = "edit"
        self.bind("<Button-1>", self._paint)
        self.bind("<Button-3>", self._erase)
        self.bind("<Configure>", lambda _event: self.redraw())

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.redraw()


    def _paint(self, event: tk.Event[tk.Misc]) -> None:
        """Add a coloured mark to the document at the clicked position.""" 
        if self.mode != "edit":
            return

        document = self.document_getter()

        x = int(event.x // self.cell_size)
        y = int(event.y // self.cell_size)

        if not (
            0 <= x < document.unit_width
            and 0 <= y < document.unit_height
        ):
            return

        source_mark = self._find_source_mark(document, x, y)

        if source_mark is not None:
            # The user clicked either the stored mark or one of its
            # symmetry-generated copies. Change the original stored mark.
            target_x = source_mark.x
            target_y = source_mark.y
        else:
            # No existing mark generated this cell, so create a new mark
            # at the clicked position.
            target_x = x
            target_y = y

        document.set_mark(
            target_x,
            target_y,
            self.active_colour_getter(),
        )

        self.on_change()

    def _erase(self, event: tk.Event[tk.Misc]) -> None:
        """Remove marks from the document when the user right-clicks on a cell."""
        if self.mode != "edit":
            return

        document = self.document_getter()

        x = int(event.x // self.cell_size)
        y = int(event.y // self.cell_size)

        if not (
            0 <= x < document.unit_width
            and 0 <= y < document.unit_height
        ):
            return

        source_mark = self._find_source_mark(document, x, y)

        if source_mark is None:
            return

        document.erase_mark(source_mark.x, source_mark.y)

        self.on_change()

    def redraw(self) -> None:
        self.delete("all")
        document = self.document_getter()
        if self.mode == "edit":
            self._draw_editor(document)
        else:
            self._draw_preview(document)

    def _fit_cell_size(self, columns: int, rows: int, maximum: int = 28) -> int:
        available_width = max(self.winfo_width(), 200)
        available_height = max(self.winfo_height(), 200)
        return max(4, min(maximum, available_width // max(columns, 1), available_height // max(rows, 1)))

    def _draw_editor(self, document: PatternDocument) -> None:
        self.cell_size = self._fit_cell_size(document.unit_width, document.unit_height)
        expanded = expand_marks(
            document.motif,
            document.unit_width,
            document.unit_height,
            document.symmetry,
        )
        expanded_positions = {(mark.x, mark.y): mark.colour_slot for mark in expanded}
        seed_positions = {(mark.x, mark.y): mark.colour_slot for mark in document.motif}

        for y in range(document.unit_height):
            for x in range(document.unit_width):
                x0, y0 = x * self.cell_size, y * self.cell_size
                colour = document.background
                if (x, y) in expanded_positions:
                    colour = document.palette[expanded_positions[(x, y)] % len(document.palette)]
                self.create_rectangle(
                    x0,
                    y0,
                    x0 + self.cell_size,
                    y0 + self.cell_size,
                    fill=colour,
                    outline="#d0d0d0",
                )
                if (x, y) in seed_positions:
                    inset = max(2, self.cell_size // 6)
                    self.create_rectangle(
                        x0 + inset,
                        y0 + inset,
                        x0 + self.cell_size - inset,
                        y0 + self.cell_size - inset,
                        outline="#202020",
                        width=2,
                    )

    def _draw_preview(self, document: PatternDocument) -> None:
        grid = build_colour_grid(document)
        rows = len(grid)
        columns = len(grid[0]) if rows else 0
        self.cell_size = self._fit_cell_size(columns, rows, maximum=18)
        for y, row in enumerate(grid):
            for x, colour in enumerate(row):
                x0, y0 = x * self.cell_size, y * self.cell_size
                self.create_rectangle(
                    x0,
                    y0,
                    x0 + self.cell_size,
                    y0 + self.cell_size,
                    fill=colour,
                    outline="#dedede",
                )
    def _find_source_mark(self, document: PatternDocument, x: int, y: int) -> Mark | None:
        """Find the stored mark responsible for a displayed cell."""

        for mark in document.motif:
            generated_marks = expand_marks(
                [mark],
                width=document.unit_width,
                height=document.unit_height,
                operations=document.symmetry,
            )

            for generated in generated_marks:
                if generated.x == x and generated.y == y:
                    return mark

        return None
