"""Tests for the drawing grid's plain-Python logic (``kvale_web.grid.scene``)."""

from __future__ import annotations

import pytest

from kvale.core import Backstitch, Mark, PatternDocument
from kvale.core.editing import (
    add_backstitch,
    add_end_piece_backstitch,
    erase_end_piece_cell,
    paint_end_piece_cell,
    set_end_piece_extension,
)
from kvale_web.grid import scene
from kvale_web.grid.scene import (
    BackstitchChain,
    LineHighlight,
    also_changed,
    backstitch_allowed,
    band_layout,
    blend,
    build_edit_scene,
    changed_pieces,
    erasable_backstitch,
    line_highlight,
    line_names,
    nearest_point,
    neighbour_source,
    parse_colour,
    piece_cells,
    piece_summary,
    region_at,
    region_rect,
    reset_loss,
    ruler_cells,
    ruler_label,
    title_key,
    view_box,
    zoom_step,
)


def document(**changes: object) -> PatternDocument:
    doc = PatternDocument(unit_width=6, unit_height=4, repeats_x=3, repeats_y=2)
    for name, value in changes.items():
        setattr(doc, name, value)
    return doc


def pixel(found: scene.EditScene, x: int, y: int) -> tuple[int, int, int]:
    box = found.box
    offset = ((y - box.y0) * box.columns + (x - box.x0)) * 4
    r, g, b = found.pixels[offset : offset + 3]
    return r, g, b


# View box ---------------------------------------------------------------------


def test_view_box_of_the_unit_is_the_unit() -> None:
    box = view_box(document(), "unit")
    assert (box.x0, box.x1, box.y0, box.y1) == (0, 5, 0, 3)
    assert box.kind_at(0, 0) == "unit" and box.kind_at(6, 0) is None
    assert box.point_allowed(6, 4) and not box.point_allowed(7, 4)


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        # (x0, x1, y0, y1, ex0, ex1, ey0, ey1); neighbour: 3 cells (half of 6), 3 rows (min 3)
        ("left", (-2, 8, 0, 3, -2, 5, 0, 3)),
        ("right", (-3, 7, 0, 3, 0, 7, 0, 3)),
        ("top", (0, 5, -1, 6, 0, 5, -1, 3)),
        ("bottom", (0, 5, -3, 4, 0, 5, 0, 4)),
        ("top_left", (-2, 8, -1, 6, -2, 5, -1, 3)),
        ("bottom_right", (-3, 7, -3, 4, 0, 7, 0, 4)),
    ],
)
def test_view_box_of_end_pieces_and_corners(target: str, expected: tuple[int, ...]) -> None:
    doc = document()
    for edge, extension in (("left", 2), ("right", 2), ("top", 1), ("bottom", 1)):
        set_end_piece_extension(doc, edge, extension)  # type: ignore[arg-type]
    box = view_box(doc, target)  # type: ignore[arg-type]
    assert (box.x0, box.x1, box.y0, box.y1, box.ex0, box.ex1, box.ey0, box.ey1) == expected


def test_kind_at_in_an_end_piece() -> None:
    doc = document()
    set_end_piece_extension(doc, "left", 2)
    box = view_box(doc, "left")
    assert box.kind_at(-1, 0) == "extra"
    assert box.kind_at(0, 0) == "unit"
    assert box.kind_at(6, 0) == "nb"
    assert not box.editable(6, 0) and box.editable(-2, 3)


def test_neighbour_source() -> None:
    # Beside an end piece: the unit, wrapped.
    assert neighbour_source("left", 6, 4, 7, 2) == ("unit", 1, 2)
    # Beside the top-left corner: right of it is the top end, below it the left end.
    assert neighbour_source("top_left", 6, 4, 7, -1) == ("top", 1, -1)
    assert neighbour_source("top_left", 6, 4, -1, 5) == ("left", -1, 1)
    assert neighbour_source("top_left", 6, 4, 7, 5) == ("unit", 1, 1)
    assert neighbour_source("bottom_right", 6, 4, -2, 1) == ("bottom", 4, 1)


# Edit scene -------------------------------------------------------------------


def test_unit_scene_colours_dims_and_marks_seeds() -> None:
    doc = document(motif=[Mark(1, 1, 0)], symmetry=["mirror_x"])
    found = build_edit_scene(doc, "unit", dim=(0, 0, 0))
    red = parse_colour(doc.palette[0])
    assert pixel(found, 1, 1) == red
    assert pixel(found, 4, 1) == blend(red, (0, 0, 0), scene.DIM_ALPHA)  # copy, outside the minimal cell
    assert pixel(found, 0, 0) == (255, 255, 255)
    assert found.restricted
    assert [(x, y) for x, y, _ in found.markers] == [(1, 1)]  # seeds only, not copies
    assert len(found.pixels) == 6 * 4 * 4


def test_end_scene_states_and_neighbours() -> None:
    doc = document(motif=[Mark(0, 0, 0), Mark(1, 0, 0)])
    set_end_piece_extension(doc, "left", 1)
    erase_end_piece_cell(doc, "left", 0, 0)
    paint_end_piece_cell(doc, "left", -1, 2, 1)
    add_backstitch(doc, (0, 0), (1, 1), 0)
    found = build_edit_scene(doc, "left")
    red, green = parse_colour(doc.palette[0]), parse_colour(doc.palette[1])
    assert pixel(found, 0, 0) == blend((255, 255, 255), red, scene.HIDDEN_ALPHA)  # unpicked here
    assert pixel(found, 1, 0) == red
    assert pixel(found, -1, 2) == green
    assert pixel(found, -1, 0) == blend((255, 255, 255), scene.EXTRA_TINT, scene.EXTRA_ALPHA)
    assert pixel(found, 6, 0) == red  # the next repeat's (0, 0), faded later by the canvas
    assert found.hidden == [(0, 0)]
    assert [(x, y) for x, y, _ in found.markers] == [(-1, 2)]
    assert found.has_extension
    # The unit's backstitch, and its copy shifted into the next repeat.
    assert [(s.x1, s.y1, s.x2, s.y2) for s in found.stitches] == [(0, 0, 1, 1)]
    assert [(s.x1, s.y1, s.x2, s.y2) for s in found.neighbour_stitches] == [(6, 0, 7, 1)]


def test_end_scene_hidden_backstitch_is_marked() -> None:
    doc = document()
    add_backstitch(doc, (0, 0), (1, 0), 0)
    from kvale.core.editing import erase_backstitch_near

    erase_backstitch_near(doc, 0.5, 0, "top")
    found = build_edit_scene(doc, "top")
    assert [s.hidden for s in found.stitches] == [True]


def test_corner_scene_starts_from_its_ends() -> None:
    doc = document()
    paint_end_piece_cell(doc, "top", 2, 0, 1)
    paint_end_piece_cell(doc, "left", 0, 2, 2)
    cells = piece_cells(doc, "top_left")
    assert cells[(2, 0)] == (1, "base") and cells[(0, 2)] == (2, "base")
    found = build_edit_scene(doc, "top_left")
    green = parse_colour(doc.palette[1])
    assert pixel(found, 2, 0) == green
    # Right of the corner: the top end piece.
    assert pixel(found, 8, 0) == green


# Backstitch ---------------------------------------------------------------------


def test_nearest_point_rounds_half_up() -> None:
    assert nearest_point(1.49, 2.5) == (1, 3)
    assert nearest_point(-0.6, -0.4) == (-1, 0)


def test_chain_carries_on_and_stops() -> None:
    chain = BackstitchChain()
    always = lambda a, b: True  # noqa: E731
    assert chain.click((0, 0), always) is None
    assert chain.click((2, 0), always) == ((0, 0), (2, 0))
    assert chain.click((2, 2), always) == ((2, 0), (2, 2))
    assert chain.pending == (2, 2)
    assert chain.click((2, 2), always) is None  # the last point again: stop
    assert chain.pending is None
    chain.click((1, 1), always)
    assert chain.stop() and not chain.stop()


def test_chain_ignores_lines_that_are_not_allowed() -> None:
    chain = BackstitchChain()
    chain.click((0, 0), lambda a, b: True)
    assert chain.click((5, 5), lambda a, b: False) is None
    assert chain.pending == (0, 0)


def test_backstitch_allowed_respects_the_minimal_cell_and_bounds() -> None:
    doc = document(symmetry=["mirror_x"])  # minimal cell: columns 0-2
    assert backstitch_allowed(doc, "unit", (0, 0), (1, 1))
    assert backstitch_allowed(doc, "unit", (3, 0), (3, 1))  # on the mirror axis
    assert not backstitch_allowed(doc, "unit", (4, 0), (5, 1))
    assert not backstitch_allowed(doc, "unit", (0, 0), (0, 0))
    assert not backstitch_allowed(doc, "unit", (0, 0), (-1, 0))
    assert backstitch_allowed(doc, "left", (5, 0), (6, 1))  # end pieces have no minimal cell
    set_end_piece_extension(doc, "left", 1)
    assert backstitch_allowed(doc, "left", (-1, 0), (0, 0))
    assert not backstitch_allowed(doc, "left", (-2, 0), (0, 0))


def test_erasable_backstitch_only_in_the_minimal_cell() -> None:
    doc = document(symmetry=["mirror_x"])
    add_backstitch(doc, (0, 0), (1, 1), 0)
    assert erasable_backstitch(doc, "unit", 0.5, 0.5) is not None
    assert erasable_backstitch(doc, "unit", 5.5, 0.5) is None  # its mirrored copy
    assert erasable_backstitch(doc, "unit", 2.5, 2.5) is None  # nothing there
    add_end_piece_backstitch(doc, "top", (4, 0), (5, 0), 1)
    assert erasable_backstitch(doc, "top", 4.5, 0) is not None


# End pieces ---------------------------------------------------------------------


def test_summary_changed_pieces_and_reset_loss() -> None:
    doc = document()
    assert changed_pieces(doc) == frozenset()
    set_end_piece_extension(doc, "right", 2)
    paint_end_piece_cell(doc, "right", 7, 0, 1)
    erase_end_piece_cell(doc, "right", 0, 0)  # empty base cell: nothing to unpick
    add_end_piece_backstitch(doc, "right", (6, 0), (7, 1), 0)
    paint_end_piece_cell(doc, "top_right", 7, 1, 2)  # in the right end's extension
    paint_end_piece_cell(doc, "top_right", 1, 1, 2)  # in the unit part: kept
    assert changed_pieces(doc) == frozenset({"right", "top_right"})
    assert piece_summary(doc, "right") == scene.PieceSummary(added=1, removed=0, lines=1, extension=2)
    loss = reset_loss(doc, "right")
    assert loss.summary.extension == 2
    assert loss.corner_stitches == 1
    assert reset_loss(doc, "top_right").corner_stitches == 0
    assert piece_summary(doc, "left").empty


def test_title_keys() -> None:
    assert title_key("left") == "end.title.left"
    assert title_key("bottom_right") == "corner.title.br"
    assert title_key("unit") == "target.unit"


# Rows and columns ---------------------------------------------------------------


def test_line_highlight_and_names_with_symmetry() -> None:
    doc = document(unit_width=6, unit_height=6, symmetry=["mirror_x"])
    removal = line_highlight(doc, "column", 1, insertion=False)
    assert removal == LineHighlight((1, 4), (), False)
    assert line_names(removal) == [("grid.colN", 2), ("grid.colN", 5)]
    insertion = line_highlight(doc, "column", 1, insertion=True)
    assert insertion == LineHighlight((1, 5), (), True)
    assert line_names(insertion) == [("grid.newColN", 2), ("grid.newColN", 7)]
    assert also_changed(doc, "column", 1, "remove") == [("grid.colN", 5)]
    assert also_changed(doc, "column", 1, "before") == [("grid.newColN", 2), ("grid.newColN", 7)]
    assert also_changed(doc, "row", 1, "after") == []  # mirror_x leaves rows alone
    diagonal = document(unit_width=4, unit_height=4, symmetry=["diag_main"])
    assert also_changed(diagonal, "row", 0, "remove") == [("grid.colN", 1)]


def test_ruler_cells() -> None:
    doc = document()
    set_end_piece_extension(doc, "left", 2)
    cells = ruler_cells(view_box(doc, "left"), "column", 24)
    assert cells[:3] == [(-2, "+2", "extra"), (-1, "+1", "extra"), (0, "1", "unit")]
    assert cells[-1] == (8, "", "nb")
    assert ruler_label(3, 40, 24) == "" and ruler_label(4, 40, 24) == "5"
    assert ruler_label(3, 12, 24) == "4" and ruler_label(3, 12, 10) == ""


# Whole band ---------------------------------------------------------------------


def test_band_layout_matches_the_renderer() -> None:
    from kvale.core import build_colour_grid

    doc = document(repeat_left_column=False)
    set_end_piece_extension(doc, "top", 2)
    layout = band_layout(doc)
    grid = build_colour_grid(doc)
    assert (layout.width, layout.height) == (len(grid[0]), len(grid))
    assert layout.x_offsets == (0, 6, 11) and layout.column_counts == (6, 5, 5)
    assert layout.y_offsets == (2, 6)


def test_regions_of_the_band() -> None:
    layout = band_layout(document(repeats_x=5, repeats_y=2))  # 30 x 8 cells
    assert region_rect(layout, "unit") == (12, 0, 6, 4)
    assert region_rect(layout, "left") == (0, 0, 6, 8)
    assert region_rect(layout, "bottom") == (0, 4, 30, 4)
    assert region_rect(layout, "top_right") == (24, 0, 6, 4)
    assert region_at(layout, 0, 0) == "top_left"
    assert region_at(layout, 29, 7) == "bottom_right"
    assert region_at(layout, 4, 1) == "left"  # inner half of the corner repeat
    assert region_at(layout, 1, 3) == "left"
    assert region_at(layout, 15, 1) == "top"
    assert region_at(layout, 15, 6) == "bottom"
    assert region_at(layout, 30, 0) is None
    single = band_layout(document(repeats_x=3, repeats_y=1))
    assert region_at(single, 9, 2) == "unit"


# Small helpers ------------------------------------------------------------------


def test_zoom_steps() -> None:
    assert zoom_step(1.0, 1) == 1.25
    assert zoom_step(1.0, -1) == 0.75
    assert zoom_step(3.0, 1) == 3.0
    assert zoom_step(0.5, -1) == 0.5


def test_parse_colour() -> None:
    assert parse_colour("#635a50") == (0x63, 0x5A, 0x50)
    assert parse_colour(" #fff ") == (255, 255, 255)
    assert parse_colour("rgb(1, 2, 3)") == (1, 2, 3)
    assert parse_colour("rgba(4 5 6 / 50%)") == (4, 5, 6)
    assert parse_colour("nonsense", (9, 9, 9)) == (9, 9, 9)


def test_paths() -> None:
    assert scene.path_rects([(1, 2, 3, 4)]) == "M1 2h3v4h-3z"
    assert scene.path_lines([(0, 0, 1.5, 2)]) == "M0 0L1.5 2"
    assert scene.path_grid(1, 1, 10, 0, 0) == "M0.5 0V10M10.5 0V10M0 0.5H10M0 10.5H10"
    outline = scene.path_outline({(0, 0), (1, 0)}, 10, 0, 0)
    assert outline.count("M") == 6  # 2 tops, 2 bottoms, 1 left, 1 right


def test_marker_colour_contrasts() -> None:
    assert scene.marker_colour("#ffffff") == "#1b1712"
    assert scene.marker_colour("#1b1b1b") == "#ffffff"


def test_backstitch_model_used_in_scene() -> None:
    doc = document(backstitches=[Backstitch(0, 0, 1, 0, 1)])
    found = build_edit_scene(doc, "unit")
    assert found.stitches[0].colour == doc.palette[1]
