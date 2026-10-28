from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

from kvale.core.editing import (
    Target,
    editor_bounds,
    get_end_piece,
    hidden_backstitches,
    intersection_in_editor,
    visible_backstitches,
)
from kvale.core.editor import Editor, EditResult
from kvale.core.model import Backstitch, Cell, PatternDocument
from kvale.core.renderer import build_backstitch_segments, build_colour_grid
from kvale.core.symmetry import expand_marks


class PatternCanvas(tk.Canvas):
    """Draws the document and turns mouse clicks into ``Editor`` calls."""

    EDIT_MARGIN = 42

    def __init__(
        self,
        master: tk.Misc,
        editor: Editor,
        active_colour_getter: Callable[[], int],
        on_change: Callable[[], None],
    ) -> None:
        super().__init__(master, background="white", highlightthickness=0)
        self.editor = editor
        self.active_colour_getter = active_colour_getter
        self.on_change = on_change
        self.cell_size = 20
        self.grid_origin_x = 0
        self.grid_origin_y = 0
        self.mode = "edit"
        self.edit_target: Target = "unit"
        self.stitch_tool = "cross"
        self.pending_backstitch_start: tuple[int, int] | None = None
        self.editor_min_x = 0
        self.editor_min_y = 0
        self.bind("<Button-1>", self._paint)
        self.bind("<Button-3>", self._erase)
        self.bind("<Motion>", self._preview_backstitch)
        self.bind("<Escape>", lambda _event: self._cancel_pending_backstitch())
        self.bind("<Configure>", lambda _event: self.redraw())

    def set_mode(self, mode: str) -> None:
        self._cancel_pending_backstitch()
        self.mode = mode
        self.redraw()

    def document_getter(self) -> PatternDocument:
        # Undo and redo replace the document object, so always read it from the editor.
        return self.editor.document

    def set_edit_target(self, target: Target) -> None:
        self._cancel_pending_backstitch()
        self.edit_target = target
        self.redraw()

    def set_stitch_tool(self, tool: str) -> None:
        self._cancel_pending_backstitch()
        self.stitch_tool = tool
        self.configure(cursor="crosshair" if tool == "backstitch" else "")
        self.redraw()

    def _event_cell(self, event: tk.Event[tk.Misc]) -> tuple[int, int]:
        display_x = int((event.x - self.grid_origin_x) // self.cell_size)
        display_y = int((event.y - self.grid_origin_y) // self.cell_size)
        return display_x + self.editor_min_x, display_y + self.editor_min_y

    def _intersection_from_event(self, event: tk.Event[tk.Misc]) -> tuple[int, int]:
        x = round((event.x - self.grid_origin_x) / self.cell_size) + self.editor_min_x
        y = round((event.y - self.grid_origin_y) / self.cell_size) + self.editor_min_y
        return int(x), int(y)

    def _intersection_in_editor(self, document: PatternDocument, point: tuple[int, int]) -> bool:
        return intersection_in_editor(document, self.edit_target, *point)

    def _changed(self, result: EditResult) -> None:
        if result.changed:
            self.on_change()

    def _cancel_pending_backstitch(self) -> None:
        self.pending_backstitch_start = None
        self.delete("pending_backstitch")

    def _preview_backstitch(self, event: tk.Event[tk.Misc]) -> None:
        self.delete("pending_backstitch")
        if self.mode != "edit" or self.stitch_tool != "backstitch" or self.pending_backstitch_start is None:
            return
        document = self.document_getter()
        end = self._intersection_from_event(event)
        if not self._intersection_in_editor(document, end):
            return
        start_x = self.grid_origin_x + (self.pending_backstitch_start[0] - self.editor_min_x) * self.cell_size
        start_y = self.grid_origin_y + (self.pending_backstitch_start[1] - self.editor_min_y) * self.cell_size
        end_x = self.grid_origin_x + (end[0] - self.editor_min_x) * self.cell_size
        end_y = self.grid_origin_y + (end[1] - self.editor_min_y) * self.cell_size
        self.create_line(
            start_x,
            start_y,
            end_x,
            end_y,
            fill=document.palette[self.active_colour_getter() % len(document.palette)],
            width=max(2, self.cell_size // 5),
            dash=(4, 2),
            tags="pending_backstitch",
        )

    def _paint(self, event: tk.Event[tk.Misc]) -> None:
        """Paint a cell, or place a backstitch end point with the backstitch tool."""
        if self.mode != "edit":
            return
        if self.stitch_tool == "backstitch":
            self._add_backstitch_point(self.document_getter(), event)
            return
        x, y = self._event_cell(event)
        self._changed(self.editor.paint(x, y, self.active_colour_getter(), self.edit_target))

    def _erase(self, event: tk.Event[tk.Misc]) -> None:
        """Erase a cell, or the nearest backstitch with the backstitch tool."""
        if self.mode != "edit":
            return
        if self.stitch_tool == "backstitch":
            self._erase_backstitch_at(event)
            return
        x, y = self._event_cell(event)
        self._changed(self.editor.erase(x, y, self.edit_target))

    def _add_backstitch_point(self, document: PatternDocument, event: tk.Event[tk.Misc]) -> None:
        self.focus_set()
        point = self._intersection_from_event(event)
        if not self._intersection_in_editor(document, point):
            return
        if self.pending_backstitch_start is None:
            self.pending_backstitch_start = point
            self._preview_backstitch(event)
            return

        start = self.pending_backstitch_start
        self._cancel_pending_backstitch()
        self._changed(
            self.editor.add_backstitch(start, point, self.active_colour_getter(), self.edit_target)
        )

    def _erase_backstitch_at(self, event: tk.Event[tk.Misc]) -> None:
        self._cancel_pending_backstitch()
        point_x = (event.x - self.grid_origin_x) / self.cell_size + self.editor_min_x
        point_y = (event.y - self.grid_origin_y) / self.cell_size + self.editor_min_y
        self._changed(self.editor.erase_backstitch_near(point_x, point_y, self.edit_target))

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
        if self.edit_target != "unit":
            self._draw_override_editor(document)
            return

        self.editor_min_x = 0
        self.editor_min_y = 0
        self.cell_size = self._fit_cell_size(document.unit_width, document.unit_height)
        grid_width = document.unit_width * self.cell_size
        grid_height = document.unit_height * self.cell_size
        self.grid_origin_x = max(self.EDIT_MARGIN, (self.winfo_width() - grid_width) // 2)
        self.grid_origin_y = max(self.EDIT_MARGIN, (self.winfo_height() - grid_height) // 2)


        expanded = expand_marks(
            document.motif,
            document.unit_width,
            document.unit_height,
            document.symmetry,
        )
        expanded_positions = {(mark.x, mark.y): mark.colour_slot for mark in expanded}
        seed_positions = {(mark.x, mark.y): mark.colour_slot for mark in document.motif}

        label_font = ("TkDefaultFont", 8)
        label_colour = "#555555"
        for x in range(document.unit_width):
            centre_x = self.grid_origin_x + (x + 0.5) * self.cell_size
            self.create_text(
                centre_x,
                self.grid_origin_y - 10,
                text=str(x + 1),
                fill=label_colour,
                font=label_font,
            )
            self.create_text(
                centre_x,
                self.grid_origin_y + grid_height + 10,
                text=str(x + 1),
                fill=label_colour,
                font=label_font,
            )
        for y in range(document.unit_height):
            centre_y = self.grid_origin_y + (y + 0.5) * self.cell_size
            self.create_text(
                self.grid_origin_x - 12,
                centre_y,
                text=str(y + 1),
                fill=label_colour,
                font=label_font,
            )
            self.create_text(
                self.grid_origin_x + grid_width + 12,
                centre_y,
                text=str(y + 1),
                fill=label_colour,
                font=label_font,
            )

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

        self._draw_local_backstitches(document, visible_backstitches(document, "unit"))

    def _draw_local_backstitches(
        self,
        document: PatternDocument,
        backstitches: list[Backstitch],
        *,
        colour_override: str | None = None,
        dash: tuple[int, int] | None = None,
    ) -> None:
        for backstitch in backstitches:
            colour = colour_override or document.palette[backstitch.colour_slot % len(document.palette)]
            self.create_line(
                self.grid_origin_x + (backstitch.start_x - self.editor_min_x) * self.cell_size,
                self.grid_origin_y + (backstitch.start_y - self.editor_min_y) * self.cell_size,
                self.grid_origin_x + (backstitch.end_x - self.editor_min_x) * self.cell_size,
                self.grid_origin_y + (backstitch.end_y - self.editor_min_y) * self.cell_size,
                fill=colour,
                width=max(2, self.cell_size // 5),
                dash=() if dash is None else dash,
            )

    def _draw_override_editor(self, document: PatternDocument) -> None:
        assert self.edit_target != "unit"
        override = get_end_piece(document, self.edit_target)
        self.editor_min_x, maximum_x, self.editor_min_y, maximum_y = editor_bounds(
            document, self.edit_target
        )
        editor_width = maximum_x - self.editor_min_x + 1
        editor_height = maximum_y - self.editor_min_y + 1
        self.cell_size = self._fit_cell_size(editor_width, editor_height)
        grid_width = editor_width * self.cell_size
        grid_height = editor_height * self.cell_size
        self.grid_origin_x = max(self.EDIT_MARGIN, (self.winfo_width() - grid_width) // 2)
        self.grid_origin_y = max(self.EDIT_MARGIN, (self.winfo_height() - grid_height) // 2)

        expanded = expand_marks(document.motif, document.unit_width, document.unit_height, document.symmetry)
        base_positions = {(mark.x, mark.y): mark.colour_slot for mark in expanded}
        removed = set(override.removed_cells) if override else set()
        additions = {(mark.x, mark.y): mark.colour_slot for mark in override.added_marks} if override else {}
        label_font = ("TkDefaultFont", 8)
        label_colour = "#555555"

        titles = {
            "top": "Øverste repetisjon",
            "bottom": "Nederste repetisjon",
            "left": "Venstre repetisjon",
            "right": "Høyre repetisjon",
        }
        self.create_text(
            self.grid_origin_x,
            self.grid_origin_y - 27,
            text=f"{titles[self.edit_target]} — høyreklikk skjuler, venstreklikk legger til/endrer",
            anchor=tk.W,
            fill="#333333",
            font=("TkDefaultFont", 9, "bold"),
        )

        for local_x in range(self.editor_min_x, maximum_x + 1):
            display_x = local_x - self.editor_min_x
            centre_x = self.grid_origin_x + (display_x + 0.5) * self.cell_size
            if local_x < 0:
                column_label = f"V{abs(local_x)}"
            elif local_x >= document.unit_width:
                column_label = f"H{local_x - document.unit_width + 1}"
            else:
                column_label = str(local_x + 1)
            for label_y in (self.grid_origin_y - 10, self.grid_origin_y + grid_height + 10):
                self.create_text(
                    centre_x,
                    label_y,
                    text=column_label,
                    fill=label_colour,
                    font=label_font,
                )

        for local_y in range(self.editor_min_y, maximum_y + 1):
            display_y = local_y - self.editor_min_y
            centre_y = self.grid_origin_y + (display_y + 0.5) * self.cell_size
            if local_y < 0:
                row_label = f"T{abs(local_y)}"
            elif local_y >= document.unit_height:
                row_label = f"B{local_y - document.unit_height + 1}"
            else:
                row_label = str(local_y + 1)
            self.create_text(
                self.grid_origin_x - 14, centre_y, text=row_label, fill=label_colour, font=label_font
            )
            self.create_text(
                self.grid_origin_x + grid_width + 14,
                centre_y,
                text=row_label,
                fill=label_colour,
                font=label_font,
            )

            for local_x in range(self.editor_min_x, maximum_x + 1):
                display_x = local_x - self.editor_min_x
                x0 = self.grid_origin_x + display_x * self.cell_size
                y0 = self.grid_origin_y + display_y * self.cell_size
                is_extension = not (
                    0 <= local_x < document.unit_width
                    and 0 <= local_y < document.unit_height
                )
                colour = "#f3f3f3" if is_extension else document.background
                base_slot = base_positions.get((local_x, local_y))
                if base_slot is not None and Cell(local_x, local_y) not in removed:
                    colour = document.palette[base_slot % len(document.palette)]
                added_slot = additions.get((local_x, local_y))
                if added_slot is not None:
                    colour = document.palette[added_slot % len(document.palette)]
                self.create_rectangle(
                    x0,
                    y0,
                    x0 + self.cell_size,
                    y0 + self.cell_size,
                    fill=colour,
                    outline="#d0d0d0",
                )
                if Cell(local_x, local_y) in removed:
                    inset = max(2, self.cell_size // 5)
                    self.create_line(
                        x0 + inset,
                        y0 + inset,
                        x0 + self.cell_size - inset,
                        y0 + self.cell_size - inset,
                        fill="#b00020",
                        width=2,
                    )
                    self.create_line(
                        x0 + self.cell_size - inset,
                        y0 + inset,
                        x0 + inset,
                        y0 + self.cell_size - inset,
                        fill="#b00020",
                        width=2,
                    )
                if added_slot is not None:
                    inset = max(2, self.cell_size // 7)
                    self.create_rectangle(
                        x0 + inset,
                        y0 + inset,
                        x0 + self.cell_size - inset,
                        y0 + self.cell_size - inset,
                        outline="#202020",
                        width=2,
                    )

        core_left = self.grid_origin_x + (0 - self.editor_min_x) * self.cell_size
        core_right = core_left + document.unit_width * self.cell_size
        core_top = self.grid_origin_y + (0 - self.editor_min_y) * self.cell_size
        core_bottom = core_top + document.unit_height * self.cell_size
        self.create_line(
            core_left,
            self.grid_origin_y,
            core_left,
            self.grid_origin_y + grid_height,
            fill="#606060",
            width=2,
        )
        self.create_line(
            core_right,
            self.grid_origin_y,
            core_right,
            self.grid_origin_y + grid_height,
            fill="#606060",
            width=2,
        )
        self.create_line(
            core_left,
            core_top,
            core_right,
            core_top,
            fill="#606060",
            width=2,
        )
        self.create_line(
            core_left,
            core_bottom,
            core_right,
            core_bottom,
            fill="#606060",
            width=2,
        )

        self._draw_local_backstitches(document, visible_backstitches(document, self.edit_target))
        self._draw_local_backstitches(
            document,
            hidden_backstitches(document, self.edit_target),
            colour_override="#b00020",
            dash=(4, 2),
        )

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
        for segment in build_backstitch_segments(document):
            self.create_line(
                segment.start_x * self.cell_size,
                segment.start_y * self.cell_size,
                segment.end_x * self.cell_size,
                segment.end_y * self.cell_size,
                fill=segment.colour,
                width=max(2, self.cell_size // 5),
            )
