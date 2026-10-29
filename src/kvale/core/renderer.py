from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from kvale.core.model import Backstitch, BackstitchKey, Mark, PatternDocument, RepeatOverride
from kvale.core.symmetry import expand_backstitches, expand_marks

if TYPE_CHECKING:
    # Pillow is imported inside render_image so that importing kvale.core
    # does not need it (for example in a browser).
    from PIL import Image


@dataclass(frozen=True)
class RenderedBackstitch:
    start_x: int
    start_y: int
    end_x: int
    end_y: int
    colour: str


def _included_column_indices(document: PatternDocument, unit_x: int) -> list[int]:
    last = document.repeats_x - 1
    keep_left = document.repeat_left_column or unit_x == 0
    keep_right = document.repeat_right_column or unit_x == last
    return [
        x
        for x in range(document.unit_width)
        if (x != 0 or keep_left) and (x != document.unit_width - 1 or keep_right)
    ]


def _included_row_indices(document: PatternDocument, unit_y: int) -> list[int]:
    last = document.repeats_y - 1
    keep_top = document.repeat_top_row or unit_y == 0
    keep_bottom = document.repeat_bottom_row or unit_y == last
    return [
        y
        for y in range(document.unit_height)
        if (y != 0 or keep_top) and (y != document.unit_height - 1 or keep_bottom)
    ]


def build_colour_grid(document: PatternDocument) -> list[list[str]]:
    document.validate()
    unit_columns = [_included_column_indices(document, unit_x) for unit_x in range(document.repeats_x)]
    unit_rows = [_included_row_indices(document, unit_y) for unit_y in range(document.repeats_y)]

    base_width = sum(len(columns) for columns in unit_columns)
    base_height = sum(len(rows) for rows in unit_rows)
    left_extension = document.left_repeat_override.extension if document.left_repeat_override else 0
    right_extension = document.right_repeat_override.extension if document.right_repeat_override else 0
    top_extension = document.top_repeat_override.extension if document.top_repeat_override else 0
    bottom_extension = document.bottom_repeat_override.extension if document.bottom_repeat_override else 0
    width = left_extension + base_width + right_extension
    height = top_extension + base_height + bottom_extension
    grid = [[document.background for _ in range(width)] for _ in range(height)]

    x_offsets: list[int] = []
    running_x = left_extension
    for columns in unit_columns:
        x_offsets.append(running_x)
        running_x += len(columns)

    y_offsets: list[int] = []
    running_y = top_extension
    for rows in unit_rows:
        y_offsets.append(running_y)
        running_y += len(rows)

    expanded = expand_marks(
        document.motif,
        document.unit_width,
        document.unit_height,
        document.symmetry,
    )

    sequences = document.palette_sequences

    def apply_override(
        marks: dict[tuple[int, int], Mark],
        override: RepeatOverride | None,
    ) -> None:
        if override is None:
            return
        for cell in override.removed_cells:
            marks.pop((cell.x, cell.y), None)
        for mark in override.added_marks:
            marks[(mark.x, mark.y)] = mark

    def mark_colour(mark: Mark, repeat_index: int) -> str:
        slot_index = mark.colour_slot % len(sequences)
        slot_sequence = sequences[slot_index]
        if document.use_palette_sequence:
            return slot_sequence[repeat_index % len(slot_sequence)]
        return slot_sequence[0]

    for unit_y in range(document.repeats_y):
        row_map = {local_y: y_offsets[unit_y] + index for index, local_y in enumerate(unit_rows[unit_y])}
        for unit_x in range(document.repeats_x):
            column_map = {
                local_x: x_offsets[unit_x] + index for index, local_x in enumerate(unit_columns[unit_x])
            }
            repeat_index = unit_y * document.repeats_x + unit_x
            unit_marks = {(mark.x, mark.y): mark for mark in expanded}
            if unit_y == 0:
                apply_override(unit_marks, document.top_repeat_override)
            if unit_y == document.repeats_y - 1:
                apply_override(unit_marks, document.bottom_repeat_override)
            if unit_x == 0:
                apply_override(unit_marks, document.left_repeat_override)
            if unit_x == document.repeats_x - 1:
                apply_override(unit_marks, document.right_repeat_override)

            for mark in unit_marks.values():
                if mark.x in column_map:
                    cell_x = column_map[mark.x]
                elif unit_x == 0 and -left_extension <= mark.x < 0:
                    cell_x = left_extension + mark.x
                elif unit_x == document.repeats_x - 1 and document.unit_width <= mark.x < (
                    document.unit_width + right_extension
                ):
                    cell_x = left_extension + base_width + mark.x - document.unit_width
                else:
                    continue
                if mark.y in row_map:
                    cell_y = row_map[mark.y]
                elif unit_y == 0 and -top_extension <= mark.y < 0:
                    cell_y = top_extension + mark.y
                elif unit_y == document.repeats_y - 1 and document.unit_height <= mark.y < (
                    document.unit_height + bottom_extension
                ):
                    cell_y = top_extension + base_height + mark.y - document.unit_height
                else:
                    continue

                grid[cell_y][cell_x] = mark_colour(mark, repeat_index)
    return grid


def build_backstitch_segments(document: PatternDocument) -> list[RenderedBackstitch]:
    document.validate()
    unit_columns = [_included_column_indices(document, unit_x) for unit_x in range(document.repeats_x)]
    unit_rows = [_included_row_indices(document, unit_y) for unit_y in range(document.repeats_y)]
    base_width = sum(len(columns) for columns in unit_columns)
    base_height = sum(len(rows) for rows in unit_rows)
    left_extension = document.left_repeat_override.extension if document.left_repeat_override else 0
    right_extension = document.right_repeat_override.extension if document.right_repeat_override else 0
    top_extension = document.top_repeat_override.extension if document.top_repeat_override else 0
    bottom_extension = document.bottom_repeat_override.extension if document.bottom_repeat_override else 0

    x_offsets: list[int] = []
    running_x = left_extension
    for columns in unit_columns:
        x_offsets.append(running_x)
        running_x += len(columns)
    y_offsets: list[int] = []
    running_y = top_extension
    for rows in unit_rows:
        y_offsets.append(running_y)
        running_y += len(rows)

    sequences = document.palette_sequences

    expanded = expand_backstitches(
        document.backstitches,
        document.unit_width,
        document.unit_height,
        document.symmetry,
    )
    rendered: dict[tuple[tuple[int, int], tuple[int, int]], RenderedBackstitch] = {}

    def apply_override(
        stitches: dict[BackstitchKey, Backstitch],
        override: RepeatOverride | None,
    ) -> None:
        if override is None:
            return
        for key in override.removed_backstitches:
            stitches.pop(key, None)
        for backstitch in override.added_backstitches:
            stitches[backstitch.key] = backstitch

    for unit_y, rows in enumerate(unit_rows):
        for unit_x, columns in enumerate(unit_columns):
            stitches = {backstitch.key: backstitch for backstitch in expanded}
            if unit_y == 0:
                apply_override(stitches, document.top_repeat_override)
            if unit_y == document.repeats_y - 1:
                apply_override(stitches, document.bottom_repeat_override)
            if unit_x == 0:
                apply_override(stitches, document.left_repeat_override)
            if unit_x == document.repeats_x - 1:
                apply_override(stitches, document.right_repeat_override)

            def map_x(local_x: int, unit_x: int = unit_x, columns: list[int] = columns) -> int | None:
                if 0 <= local_x <= document.unit_width:
                    return x_offsets[unit_x] + sum(column < local_x for column in columns)
                if unit_x == 0 and -left_extension <= local_x < 0:
                    return left_extension + local_x
                if (
                    unit_x == document.repeats_x - 1
                    and document.unit_width < local_x <= document.unit_width + right_extension
                ):
                    return left_extension + base_width + local_x - document.unit_width
                return None

            def map_y(local_y: int, unit_y: int = unit_y, rows: list[int] = rows) -> int | None:
                if 0 <= local_y <= document.unit_height:
                    return y_offsets[unit_y] + sum(row < local_y for row in rows)
                if unit_y == 0 and -top_extension <= local_y < 0:
                    return top_extension + local_y
                if (
                    unit_y == document.repeats_y - 1
                    and document.unit_height < local_y <= document.unit_height + bottom_extension
                ):
                    return top_extension + base_height + local_y - document.unit_height
                return None

            repeat_index = unit_y * document.repeats_x + unit_x
            for backstitch in stitches.values():
                start_x = map_x(backstitch.start_x)
                start_y = map_y(backstitch.start_y)
                end_x = map_x(backstitch.end_x)
                end_y = map_y(backstitch.end_y)
                if start_x is None or start_y is None or end_x is None or end_y is None:
                    continue
                start: tuple[int, int] = (start_x, start_y)
                end: tuple[int, int] = (end_x, end_y)
                if start == end:
                    continue
                key = (start, end) if start <= end else (end, start)
                slot = backstitch.colour_slot % len(sequences)
                sequence = sequences[slot]
                colour = sequence[repeat_index % len(sequence)] if document.use_palette_sequence else sequence[0]
                rendered[key] = RenderedBackstitch(start[0], start[1], end[0], end[1], colour)
    return list(rendered.values())


def render_image(
    document: PatternDocument,
    cell_size: int = 16,
    draw_grid: bool = True,
    grid_colour: str = "#d8d8d8",
) -> Image.Image:
    from PIL import Image, ImageDraw

    grid = build_colour_grid(document)
    rows = len(grid)
    columns = len(grid[0]) if rows else 0
    image = Image.new("RGB", (columns * cell_size, rows * cell_size), document.background)
    draw = ImageDraw.Draw(image)

    for y, row in enumerate(grid):
        for x, colour in enumerate(row):
            x0 = x * cell_size
            y0 = y * cell_size
            draw.rectangle((x0, y0, x0 + cell_size - 1, y0 + cell_size - 1), fill=colour)

    if draw_grid:
        for x in range(columns + 1):
            xx = x * cell_size
            draw.line((xx, 0, xx, rows * cell_size), fill=grid_colour)
        for y in range(rows + 1):
            yy = y * cell_size
            draw.line((0, yy, columns * cell_size, yy), fill=grid_colour)

    line_width = max(2, cell_size // 5)
    for segment in build_backstitch_segments(document):
        draw.line(
            (
                segment.start_x * cell_size,
                segment.start_y * cell_size,
                segment.end_x * cell_size,
                segment.end_y * cell_size,
            ),
            fill=segment.colour,
            width=line_width,
        )

    return image
