from __future__ import annotations

from PIL import Image, ImageDraw

from kvale.core.colouring import resolve_colour_index
from kvale.core.model import PatternDocument
from kvale.core.symmetry import expand_marks


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

    width = sum(len(columns) for columns in unit_columns)
    height = sum(len(rows) for rows in unit_rows)
    grid = [[document.background for _ in range(width)] for _ in range(height)]

    x_offsets: list[int] = []
    running_x = 0
    for columns in unit_columns:
        x_offsets.append(running_x)
        running_x += len(columns)

    y_offsets: list[int] = []
    running_y = 0
    for rows in unit_rows:
        y_offsets.append(running_y)
        running_y += len(rows)

    expanded = expand_marks(
        document.motif,
        document.unit_width,
        document.unit_height,
        document.symmetry,
    )

    for unit_y in range(document.repeats_y):
        row_map = {local_y: y_offsets[unit_y] + index for index, local_y in enumerate(unit_rows[unit_y])}
        for unit_x in range(document.repeats_x):
            column_map = {
                local_x: x_offsets[unit_x] + index for index, local_x in enumerate(unit_columns[unit_x])
            }
            for mark in expanded:
                if mark.x not in column_map:
                    continue
                if mark.y not in row_map:
                    continue

                cell_x = column_map[mark.x]
                cell_y = row_map[mark.y]
                index = resolve_colour_index(
                    mark.colour_slot,
                    unit_x,
                    unit_y,
                    cell_x,
                    cell_y,
                    document.colour_rule,
                    len(document.palette),
                )
                grid[cell_y][cell_x] = document.palette[index]
    return grid


def render_image(
    document: PatternDocument,
    cell_size: int = 16,
    draw_grid: bool = True,
    grid_colour: str = "#d8d8d8",
) -> Image.Image:
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

    return image
