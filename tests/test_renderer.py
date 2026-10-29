import os
import subprocess
import sys

from kvale.core.model import Mark, PatternDocument
from kvale.core.renderer import build_colour_grid, render_image


def test_core_import_does_not_load_pillow() -> None:
    # The browser app imports kvale.core before Pillow is downloaded.
    code = "import sys, kvale.core; assert 'PIL' not in sys.modules"
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)}
    subprocess.run([sys.executable, "-c", code], check=True, env=env)


def test_render_image_size() -> None:
    document = PatternDocument(unit_width=2, unit_height=3, repeats_x=2, repeats_y=1)
    image = render_image(document, cell_size=4)
    assert image.size == (2 * 2 * 4, 3 * 4)


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


def test_palette_sequence_off_uses_first_sequence_colour_for_all_repeats() -> None:
    document = PatternDocument(
        unit_width=1,
        unit_height=1,
        repeats_x=5,
        repeats_y=1,
        motif=[Mark(0, 0, 0)],
        symmetry=["identity"],
        palette_sequences=[["#ff0000", "#0000ff"]],
        use_palette_sequence=False,
    )

    grid = build_colour_grid(document)
    assert grid[0] == ["#ff0000", "#ff0000", "#ff0000", "#ff0000", "#ff0000"]


def test_palette_sequence_on_cycles_along_repeats() -> None:
    document = PatternDocument(
        unit_width=1,
        unit_height=1,
        repeats_x=6,
        repeats_y=1,
        motif=[Mark(0, 0, 0)],
        symmetry=["identity"],
        palette_sequences=[["#ff0000", "#0000ff", "#00ff00"]],
        use_palette_sequence=True,
    )

    grid = build_colour_grid(document)
    assert grid[0] == ["#ff0000", "#0000ff", "#00ff00", "#ff0000", "#0000ff", "#00ff00"]


def test_palette_sequence_single_entry_stays_constant_when_enabled() -> None:
    document = PatternDocument(
        unit_width=1,
        unit_height=1,
        repeats_x=4,
        repeats_y=1,
        motif=[Mark(0, 0, 0)],
        symmetry=["identity"],
        palette_sequences=[["#123456"]],
        use_palette_sequence=True,
    )

    grid = build_colour_grid(document)
    assert grid[0] == ["#123456", "#123456", "#123456", "#123456"]


def test_palette_sequences_are_applied_per_colour_slot() -> None:
    document = PatternDocument(
        unit_width=2,
        unit_height=1,
        repeats_x=4,
        repeats_y=1,
        motif=[Mark(0, 0, 0), Mark(1, 0, 1)],
        symmetry=["identity"],
        palette_sequences=[["#ff0000", "#00ff00"], ["#0000ff"]],
        use_palette_sequence=True,
    )

    grid = build_colour_grid(document)
    assert grid[0] == [
        "#ff0000", "#0000ff",
        "#00ff00", "#0000ff",
        "#ff0000", "#0000ff",
        "#00ff00", "#0000ff",
    ]
