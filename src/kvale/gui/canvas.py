from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from math import hypot
from typing import cast

from kvale.core.model import Backstitch, BackstitchKey, Cell, Mark, PatternDocument, RepeatOverride
from kvale.core.renderer import build_backstitch_segments, build_colour_grid
from kvale.core.symmetry import expand_backstitches, expand_marks


class PatternCanvas(tk.Canvas):
    EDIT_MARGIN = 42

    def __init__(
        self,
        master: tk.Misc,
        document_getter: Callable[[], PatternDocument],
        active_colour_getter: Callable[[], int],
        on_before_change: Callable[[], None],
        on_change: Callable[[], None],
        on_insert_column: Callable[[int], None],
        on_remove_column: Callable[[int], None],
        on_insert_row: Callable[[int], None],
        on_remove_row: Callable[[int], None],
    ) -> None:
        super().__init__(master, background="white", highlightthickness=0)
        self.document_getter = document_getter
        self.active_colour_getter = active_colour_getter
        self.on_before_change = on_before_change
        self.on_change = on_change
        self.on_insert_column = on_insert_column
        self.on_remove_column = on_remove_column
        self.on_insert_row = on_insert_row
        self.on_remove_row = on_remove_row
        self.cell_size = 20
        self.grid_origin_x = 0
        self.grid_origin_y = 0
        self.action_areas: list[tuple[tuple[int, int, int, int], str]] = []
        self.mode = "edit"
        self.edit_target = "unit"
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

    def set_edit_target(self, target: str) -> None:
        self._cancel_pending_backstitch()
        self.edit_target = target
        self.redraw()

    def set_stitch_tool(self, tool: str) -> None:
        self._cancel_pending_backstitch()
        self.stitch_tool = tool
        self.configure(cursor="crosshair" if tool == "backstitch" else "")
        self.redraw()

    def _override(self, document: PatternDocument, *, create: bool = False) -> RepeatOverride | None:
        attribute = f"{self.edit_target}_repeat_override"
        override = cast(RepeatOverride | None, getattr(document, attribute))
        if override is None and create:
            override = RepeatOverride()
            setattr(document, attribute, override)
        return override

    def _ensure_override(self, document: PatternDocument) -> RepeatOverride:
        override = self._override(document, create=True)
        assert override is not None
        return override

    def _event_cell(self, event: tk.Event[tk.Misc]) -> tuple[int, int]:
        display_x = int((event.x - self.grid_origin_x) // self.cell_size)
        display_y = int((event.y - self.grid_origin_y) // self.cell_size)
        return display_x + self.editor_min_x, display_y + self.editor_min_y

    def _editor_bounds(self, document: PatternDocument) -> tuple[int, int, int, int]:
        if self.edit_target == "unit":
            return 0, document.unit_width - 1, 0, document.unit_height - 1
        override = self._override(document)
        extension = override.extension if override else 0
        minimum_x = -extension if self.edit_target == "left" else 0
        maximum_x = (
            document.unit_width + extension - 1
            if self.edit_target == "right"
            else document.unit_width - 1
        )
        if self.edit_target == "top":
            return minimum_x, maximum_x, -extension, document.unit_height - 1
        maximum_y = (
            document.unit_height + extension - 1
            if self.edit_target == "bottom"
            else document.unit_height - 1
        )
        return minimum_x, maximum_x, 0, maximum_y

    def _intersection_from_event(self, event: tk.Event[tk.Misc]) -> tuple[int, int]:
        x = round((event.x - self.grid_origin_x) / self.cell_size) + self.editor_min_x
        y = round((event.y - self.grid_origin_y) / self.cell_size) + self.editor_min_y
        return int(x), int(y)

    def _intersection_in_editor(self, document: PatternDocument, point: tuple[int, int]) -> bool:
        minimum_x, maximum_x, minimum_y, maximum_y = self._editor_bounds(document)
        return minimum_x <= point[0] <= maximum_x + 1 and minimum_y <= point[1] <= maximum_y + 1

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
        """Add a mark, or apply hover action when clicking margin controls."""
        if self.mode != "edit":
            return

        document = self.document_getter()
        if self.stitch_tool == "backstitch":
            self._add_backstitch_point(document, event)
            return


        x, y = self._event_cell(event)
        minimum_x, maximum_x, minimum_y, maximum_y = self._editor_bounds(document)

        if not (
            minimum_x <= x <= maximum_x
            and minimum_y <= y <= maximum_y
        ):
            return

        if self.edit_target != "unit":
            expanded = expand_marks(document.motif, document.unit_width, document.unit_height, document.symmetry)
            base_colour = next(
                (mark.colour_slot for mark in expanded if mark.x == x and mark.y == y),
                None,
            )
            override = self._override(document)
            active_colour = self.active_colour_getter()
            existing = next(
                (mark for mark in override.added_marks if mark.x == x and mark.y == y),
                None,
            ) if override else None
            removed = Cell(x, y) in override.removed_cells if override else False
            if existing is not None and existing.colour_slot == active_colour:
                return
            if existing is None and not removed and base_colour == active_colour:
                return

            self.on_before_change()
            override = self._ensure_override(document)
            if base_colour == active_colour:
                override.removed_cells = [
                    cell for cell in override.removed_cells if not (cell.x == x and cell.y == y)
                ]
                override.remove_added_mark(x, y)
            else:
                override.set_mark(x, y, active_colour)
            self.on_change()
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

        if source_mark is not None and source_mark.colour_slot == self.active_colour_getter():
            return

        self.on_before_change()
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
        if self.stitch_tool == "backstitch":
            self._erase_backstitch_at(document, event)
            return


        x, y = self._event_cell(event)
        minimum_x, maximum_x, minimum_y, maximum_y = self._editor_bounds(document)

        if not (
            minimum_x <= x <= maximum_x
            and minimum_y <= y <= maximum_y
        ):
            return

        if self.edit_target != "unit":
            expanded = expand_marks(document.motif, document.unit_width, document.unit_height, document.symmetry)
            has_base = any(mark.x == x and mark.y == y for mark in expanded)
            override = self._override(document)
            has_added = bool(
                override and any(mark.x == x and mark.y == y for mark in override.added_marks)
            )
            is_removed = bool(override and Cell(x, y) in override.removed_cells)
            if (not has_base and not has_added) or (has_base and is_removed and not has_added):
                return

            self.on_before_change()
            override = self._ensure_override(document)
            if 0 <= x < document.unit_width and 0 <= y < document.unit_height and has_base:
                override.hide_cell(x, y)
            else:
                override.remove_added_mark(x, y)
            self.on_change()
            return

        source_mark = self._find_source_mark(document, x, y)

        if source_mark is None:
            return

        self.on_before_change()
        document.erase_mark(source_mark.x, source_mark.y)

        self.on_change()

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
        if start == point:
            return
        candidate = Backstitch(start[0], start[1], point[0], point[1], self.active_colour_getter())

        if self.edit_target == "unit":
            source = self._find_source_backstitch(document, candidate.key)
            if source is not None and source.colour_slot == candidate.colour_slot:
                return
            if source is not None:
                candidate = Backstitch(
                    source.start_x,
                    source.start_y,
                    source.end_x,
                    source.end_y,
                    candidate.colour_slot,
                )
            self.on_before_change()
            document.set_backstitch(candidate)
            self.on_change()
            return

        expanded = {
            item.key: item
            for item in expand_backstitches(
                document.backstitches,
                document.unit_width,
                document.unit_height,
                document.symmetry,
            )
        }
        override = self._override(document)
        base = expanded.get(candidate.key)
        existing = next(
            (item for item in override.added_backstitches if item.key == candidate.key),
            None,
        ) if override else None
        removed = candidate.key in override.removed_backstitches if override else False
        if existing is not None and existing.colour_slot == candidate.colour_slot:
            return
        if existing is None and not removed and base is not None and base.colour_slot == candidate.colour_slot:
            return

        self.on_before_change()
        override = self._ensure_override(document)
        if base is not None and base.colour_slot == candidate.colour_slot:
            override.restore_backstitch(candidate.key)
        else:
            override.set_backstitch(candidate)
        self.on_change()

    @staticmethod
    def _distance_to_segment(
        point_x: float,
        point_y: float,
        backstitch: Backstitch,
    ) -> float:
        start_x, start_y = backstitch.start_x, backstitch.start_y
        delta_x = backstitch.end_x - start_x
        delta_y = backstitch.end_y - start_y
        length_squared = delta_x * delta_x + delta_y * delta_y
        if length_squared == 0:
            return hypot(point_x - start_x, point_y - start_y)
        amount = ((point_x - start_x) * delta_x + (point_y - start_y) * delta_y) / length_squared
        amount = max(0.0, min(1.0, amount))
        nearest_x = start_x + amount * delta_x
        nearest_y = start_y + amount * delta_y
        return hypot(point_x - nearest_x, point_y - nearest_y)

    def _erase_backstitch_at(self, document: PatternDocument, event: tk.Event[tk.Misc]) -> None:
        self._cancel_pending_backstitch()
        point_x = (event.x - self.grid_origin_x) / self.cell_size + self.editor_min_x
        point_y = (event.y - self.grid_origin_y) / self.cell_size + self.editor_min_y
        expanded = expand_backstitches(
            document.backstitches,
            document.unit_width,
            document.unit_height,
            document.symmetry,
        )

        if self.edit_target == "unit":
            candidates = expanded
        else:
            override = self._override(document)
            stitches = {item.key: item for item in expanded}
            if override is not None:
                for key in override.removed_backstitches:
                    stitches.pop(key, None)
                for item in override.added_backstitches:
                    stitches[item.key] = item
            candidates = list(stitches.values())
        if not candidates:
            return

        nearest = min(candidates, key=lambda item: self._distance_to_segment(point_x, point_y, item))
        if self._distance_to_segment(point_x, point_y, nearest) > 0.35:
            return

        if self.edit_target == "unit":
            source = self._find_source_backstitch(document, nearest.key)
            if source is None:
                return
            self.on_before_change()
            document.erase_backstitch(source.key)
        else:
            override = self._override(document)
            base_keys = {item.key for item in expanded}
            self.on_before_change()
            override = self._ensure_override(document)
            if nearest.key in base_keys:
                override.hide_backstitch(nearest.key)
            else:
                override.added_backstitches = [
                    item for item in override.added_backstitches if item.key != nearest.key
                ]
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

        self._draw_local_backstitches(
            document,
            expand_backstitches(
                document.backstitches,
                document.unit_width,
                document.unit_height,
                document.symmetry,
            ),
        )

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
        override = self._override(document)
        extension = override.extension if override else 0
        self.editor_min_x = -extension if self.edit_target == "left" else 0
        maximum_x = (
            document.unit_width + extension - 1
            if self.edit_target == "right"
            else document.unit_width - 1
        )
        self.editor_min_y = -extension if self.edit_target == "top" else 0
        maximum_y = (
            document.unit_height + extension - 1
            if self.edit_target == "bottom"
            else document.unit_height - 1
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

        expanded_backstitches = expand_backstitches(
            document.backstitches,
            document.unit_width,
            document.unit_height,
            document.symmetry,
        )
        visible = {item.key: item for item in expanded_backstitches}
        if override is not None:
            for key in override.removed_backstitches:
                visible.pop(key, None)
            for item in override.added_backstitches:
                visible[item.key] = item
        self._draw_local_backstitches(document, list(visible.values()))
        if override is not None:
            base = {item.key: item for item in expanded_backstitches}
            hidden = [base[key] for key in override.removed_backstitches if key in base]
            self._draw_local_backstitches(
                document,
                hidden,
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

    def _find_source_backstitch(
        self,
        document: PatternDocument,
        key: BackstitchKey,
    ) -> Backstitch | None:
        for backstitch in document.backstitches:
            generated = expand_backstitches(
                [backstitch],
                document.unit_width,
                document.unit_height,
                document.symmetry,
            )
            if any(item.key == key for item in generated):
                return backstitch
        return None
