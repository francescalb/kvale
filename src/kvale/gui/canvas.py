from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

from kvale.core.model import Mark, PatternDocument
from kvale.core.renderer import build_colour_grid
from kvale.core.symmetry import expand_marks


class PatternCanvas(tk.Canvas):
    EDIT_MARGIN = 28

    def __init__(
        self,
        master: tk.Misc,
        document_getter: Callable[[], PatternDocument],
        active_colour_getter: Callable[[], int],
        on_change: Callable[[], None],
        on_insert_column: Callable[[int], None],
        on_remove_column: Callable[[int], None],
        on_insert_row: Callable[[int], None],
        on_remove_row: Callable[[int], None],
    ) -> None:
        super().__init__(master, background="white", highlightthickness=0)
        self.document_getter = document_getter
        self.active_colour_getter = active_colour_getter
        self.on_change = on_change
        self.on_insert_column = on_insert_column
        self.on_remove_column = on_remove_column
        self.on_insert_row = on_insert_row
        self.on_remove_row = on_remove_row
        self.cell_size = 20
        self.grid_origin_x = 0
        self.grid_origin_y = 0
        self.hover_target: tuple[str, int, str] | None = None
        self.action_areas: list[tuple[tuple[int, int, int, int], str]] = []
        self.mode = "edit"
        self.bind("<Button-1>", self._paint)
        self.bind("<Button-3>", self._erase)
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Configure>", lambda _event: self.redraw())

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.redraw()


    def _paint(self, event: tk.Event[tk.Misc]) -> None:
        """Add a mark, or apply hover action when clicking margin controls."""
        if self.mode != "edit":
            return

        document = self.document_getter()

        if self._apply_hover_action(event.x, event.y, is_add=True):
            return

        x = int((event.x - self.grid_origin_x) // self.cell_size)
        y = int((event.y - self.grid_origin_y) // self.cell_size)

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
        """Erase a mark, or apply hover action when clicking margin controls."""
        if self.mode != "edit":
            return

        document = self.document_getter()

        if self._apply_hover_action(event.x, event.y, is_add=False):
            return

        x = int((event.x - self.grid_origin_x) // self.cell_size)
        y = int((event.y - self.grid_origin_y) // self.cell_size)

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
        available_width = max(self.winfo_width() - 2 * self.EDIT_MARGIN, 200)
        available_height = max(self.winfo_height() - 2 * self.EDIT_MARGIN, 200)
        return max(4, min(maximum, available_width // max(columns, 1), available_height // max(rows, 1)))

    def _draw_editor(self, document: PatternDocument) -> None:
        self.cell_size = self._fit_cell_size(document.unit_width, document.unit_height)
        grid_width = document.unit_width * self.cell_size
        grid_height = document.unit_height * self.cell_size
        self.grid_origin_x = max(self.EDIT_MARGIN, (self.winfo_width() - grid_width) // 2)
        self.grid_origin_y = max(self.EDIT_MARGIN, (self.winfo_height() - grid_height) // 2)

        self._draw_resize_guides(document)

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
                x0 = self.grid_origin_x + x * self.cell_size
                y0 = self.grid_origin_y + y * self.cell_size
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

        # Draw hover actions last so they are never hidden behind cells.
        if self.hover_target is not None:
            self._draw_hover_actions(document)

    def _draw_preview(self, document: PatternDocument) -> None:
        self.grid_origin_x = 0
        self.grid_origin_y = 0
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

    def _draw_resize_guides(self, document: PatternDocument) -> None:
        self.action_areas = []
        x0 = self.grid_origin_x
        y0 = self.grid_origin_y
        x1 = x0 + document.unit_width * self.cell_size
        y1 = y0 + document.unit_height * self.cell_size

        self.create_rectangle(x0, y0 - self.EDIT_MARGIN, x1, y0, fill="#eef6ff", outline="")
        self.create_rectangle(x0, y1, x1, y1 + self.EDIT_MARGIN, fill="#eef6ff", outline="")
        self.create_rectangle(x0 - self.EDIT_MARGIN, y0, x0, y1, fill="#eef6ff", outline="")
        self.create_rectangle(x1, y0, x1 + self.EDIT_MARGIN, y1, fill="#eef6ff", outline="")

    def _resize_target(self, document: PatternDocument, px: int, py: int) -> tuple[str, int, str] | None:
        x0 = self.grid_origin_x
        y0 = self.grid_origin_y
        x1 = x0 + document.unit_width * self.cell_size
        y1 = y0 + document.unit_height * self.cell_size

        # Top and bottom margins operate on columns.
        if x0 <= px < x1 and y0 - self.EDIT_MARGIN <= py < y0:
            col = min(document.unit_width - 1, max(0, (px - x0) // self.cell_size))
            return ("column", int(col), "top")
        if x0 <= px < x1 and y1 <= py < y1 + self.EDIT_MARGIN:
            col = min(document.unit_width - 1, max(0, (px - x0) // self.cell_size))
            return ("column", int(col), "bottom")

        # Left and right margins operate on rows.
        if y0 <= py < y1 and x0 - self.EDIT_MARGIN <= px < x0:
            row = min(document.unit_height - 1, max(0, (py - y0) // self.cell_size))
            return ("row", int(row), "left")
        if y0 <= py < y1 and x1 <= px < x1 + self.EDIT_MARGIN:
            row = min(document.unit_height - 1, max(0, (py - y0) // self.cell_size))
            return ("row", int(row), "right")

        return None

    def _on_motion(self, event: tk.Event[tk.Misc]) -> None:
        if self.mode != "edit":
            return

        document = self.document_getter()
        new_target = self._resize_target(document, event.x, event.y)

        # If pointer is on a margin, that position should always control target.
        if new_target is not None:
            if new_target != self.hover_target:
                self.hover_target = new_target
                self.redraw()
            return

        # Keep current target while user moves inside action boxes.
        if self._is_in_action_area(event.x, event.y):
            return

        if self.hover_target is not None:
            self.hover_target = None
            self.redraw()

    def _on_leave(self, _event: tk.Event[tk.Misc]) -> None:
        if self.hover_target is None:
            return
        self.hover_target = None
        self.action_areas = []
        self.redraw()

    def _draw_hover_actions(self, document: PatternDocument) -> None:
        if self.hover_target is None:
            return

        axis, index, side = self.hover_target
        box_w = 92
        box_h = 22
        gap = 4

        if axis == "column":
            anchor_x = self.grid_origin_x + index * self.cell_size + self.cell_size // 2
            labels = [
                ("+/- Foran", "before"),
                ("+/- Bak", "after"),
            ]
        else:
            anchor_y = self.grid_origin_y + index * self.cell_size + self.cell_size // 2
            labels = [
                ("+/- Over", "before"),
                ("+/- Under", "after"),
            ]

        total_h = len(labels) * box_h + (len(labels) - 1) * gap
        x0 = self.grid_origin_x
        y0 = self.grid_origin_y
        x1 = x0 + document.unit_width * self.cell_size
        y1 = y0 + document.unit_height * self.cell_size

        if axis == "column":
            start_x = anchor_x - box_w // 2
            if side == "top":
                start_y = y0 - total_h
            else:
                start_y = y1
        else:
            start_y = anchor_y - total_h // 2
            if side == "left":
                start_x = x0 - box_w
            else:
                start_x = x1

        start_x = max(2, min(self.winfo_width() - box_w - 2, start_x))
        start_y = max(2, min(self.winfo_height() - total_h - 2, start_y))

        for idx, (text, action_name) in enumerate(labels):
            y0 = start_y + idx * (box_h + gap)
            x0 = start_x
            x1 = x0 + box_w
            y1 = y0 + box_h
            fill = "#f9fbff" if idx % 2 == 0 else "#f1f6ff"
            self.create_rectangle(x0, y0, x1, y1, fill=fill, outline="#9aa8bf")
            self.create_text((x0 + x1) // 2, (y0 + y1) // 2, text=text)
            self.action_areas.append(((x0, y0, x1, y1), f"{axis}:{index}:{action_name}"))

    def _is_in_action_area(self, px: int, py: int) -> bool:
        for (x0, y0, x1, y1), _action in self.action_areas:
            if x0 <= px <= x1 and y0 <= py <= y1:
                return True
        return False

    def _apply_hover_action(self, px: int, py: int, is_add: bool) -> bool:
        for (x0, y0, x1, y1), action in self.action_areas:
            if x0 <= px <= x1 and y0 <= py <= y1:
                axis, index_raw, placement = action.split(":")
                index = int(index_raw)

                if axis == "column":
                    if placement == "before":
                        target_index = index
                    else:
                        target_index = min(index + 1, self.document_getter().unit_width)

                    if is_add:
                        self.on_insert_column(target_index)
                    else:
                        remove_index = min(target_index, self.document_getter().unit_width - 1)
                        self.on_remove_column(remove_index)
                else:
                    if placement == "before":
                        target_index = index
                    else:
                        target_index = min(index + 1, self.document_getter().unit_height)

                    if is_add:
                        self.on_insert_row(target_index)
                    else:
                        remove_index = min(target_index, self.document_getter().unit_height - 1)
                        self.on_remove_row(remove_index)

                return True
        return False
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
