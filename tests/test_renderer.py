from kvale.core.model import Mark, PatternDocument
from kvale.core.renderer import build_colour_grid


def test_disable_horizontal_edge_repetition() -> None:
    document = PatternDocument(
        unit_width=3,
        unit_height=2,
        repeats_x=3,
        repeats_y=1,
        motif=[Mark(0, 0, 0), Mark(1, 0, 0), Mark(2, 0, 0)],
        symmetry=["identity"],
    )
    document.repeat_left_column = False
    document.repeat_right_column = False

    grid = build_colour_grid(document)

    # Width is compacted: 2 (first unit) + 1 (middle) + 2 (last unit) = 5.
    assert len(grid[0]) == 5
    # No artificial white seam columns remain in the repeated band.
    assert all(colour == document.palette[0] for colour in grid[0])


def test_disable_vertical_edge_repetition() -> None:
    document = PatternDocument(
        unit_width=2,
        unit_height=3,
        repeats_x=1,
        repeats_y=3,
        motif=[Mark(1, 0, 1), Mark(1, 1, 1), Mark(1, 2, 1)],
        symmetry=["identity"],
    )
    document.repeat_top_row = False
    document.repeat_bottom_row = False

    grid = build_colour_grid(document)

    # Height is compacted: 2 (first unit) + 1 (middle) + 2 (last unit) = 5.
    assert len(grid) == 5
    # No artificial white seam rows remain in the repeated band.
    assert all(row[1] == document.palette[1] for row in grid)
