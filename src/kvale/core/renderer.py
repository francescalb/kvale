from __future__ import annotations

from PIL import Image, ImageDraw

from kvale.core.colouring import resolve_colour_index
from kvale.core.model import PatternDocument
from kvale.core.symmetry import expand_marks


def build_colour_grid(document: PatternDocument) -> list[list[str]]:
    document.validate()
    width = document.unit_width * document.repeats_x
    height = document.unit_height * document.repeats_y
    grid = [[document.background for _ in range(width)] for _ in range(height)]
    expanded = expand_marks(
        document.motif,
        document.unit_width,
        document.unit_height,
        document.symmetry,
    )

    for unit_y in range(document.repeats_y):
        for unit_x in range(document.repeats_x):
            for mark in expanded:
                cell_x = unit_x * document.unit_width + mark.x
                cell_y = unit_y * document.unit_height + mark.y
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
