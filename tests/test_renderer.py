import os
import subprocess
import sys
from typing import Any

from PIL import Image

from kvale.core.model import Mark, PatternDocument
from kvale.core.renderer import (
    KEY_CHIP,
    KEY_CHIP_GAP,
    KEY_COLUMN_GAP,
    KEY_FONT_SIZE,
    KEY_PADDING,
    KEY_ROW_GAP,
    _key_font,
    build_colour_grid,
    key_layout,
    render_image,
    render_image_with_key,
)


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


# Thread key under the band (render_image_with_key) ---------------------


def test_key_layout_keeps_a_wide_band_and_fills_columns() -> None:
    layout = key_layout(1000, 200, [100, 80, 120], title_width=150, title_height=20, text_height=14)
    column = KEY_CHIP + KEY_CHIP_GAP + 120
    assert layout.width == 1000
    assert layout.columns == 3
    assert layout.title_top == 200 + KEY_PADDING
    first_row = layout.title_top + 20 + KEY_ROW_GAP
    assert layout.positions == (
        (KEY_PADDING, first_row),
        (KEY_PADDING + column + KEY_COLUMN_GAP, first_row),
        (KEY_PADDING + 2 * (column + KEY_COLUMN_GAP), first_row),
    )
    assert layout.height == first_row + KEY_CHIP + KEY_PADDING


def test_key_layout_widens_a_narrow_band_and_wraps_rows() -> None:
    layout = key_layout(40, 40, [200, 200, 200], text_height=14)
    assert layout.width == KEY_CHIP + KEY_CHIP_GAP + 200 + 2 * KEY_PADDING
    assert layout.columns == 1
    assert [y for _x, y in layout.positions] == [
        40 + KEY_PADDING + line * (KEY_CHIP + KEY_ROW_GAP) for line in range(3)
    ]
    # A long title widens the image too.
    assert key_layout(40, 40, [10], title_width=500, title_height=20).width == 500 + 2 * KEY_PADDING


def _colour_count(image: Image.Image, colour: tuple[int, int, int]) -> int:
    counts: list[tuple[int, Any]] = image.convert("RGB").getcolors(1 << 20) or []
    return sum(count for count, found in counts if found == colour)


def test_render_image_with_key_lists_the_threads_under_the_band() -> None:
    document = PatternDocument(unit_width=4, unit_height=2, repeats_x=6, repeats_y=1)
    band = render_image(document, cell_size=16)
    rows = [("#c72b3b", "DMC 321 – Red"), ("#123456", "Egen farge #123456")]
    image = render_image_with_key(document, rows, title="Garn i mønsteret", cell_size=16)
    assert image.width >= band.width
    assert image.height > band.height
    # The band is unchanged at the top, and each row has a chip of its colour below.
    assert image.crop((0, 0, band.width, band.height)).tobytes() == band.tobytes()
    key = image.crop((0, band.height, image.width, image.height))
    assert _colour_count(key, (0xC7, 0x2B, 0x3B)) >= (KEY_CHIP - 2) ** 2
    assert _colour_count(key, (0x12, 0x34, 0x56)) >= (KEY_CHIP - 2) ** 2
    assert key.getpixel((key.width - 1, key.height - 1)) == (255, 255, 255)
    # There is text: some dark pixels besides the chips.
    assert _colour_count(key, (0x1B, 0x17, 0x12)) > 0


def test_render_image_with_key_without_rows_is_the_band() -> None:
    document = PatternDocument(unit_width=3, unit_height=3, repeats_x=2, repeats_y=1)
    image = render_image_with_key(document, [], title="Threads", cell_size=8)
    assert image.tobytes() == render_image(document, cell_size=8).tobytes()


def test_key_font_has_norwegian_and_italian_letters() -> None:
    from PIL import ImageDraw, ImageFont

    font = _key_font(KEY_FONT_SIZE)
    assert isinstance(font, ImageFont.FreeTypeFont)
    assert font.getname()[0] == "Atkinson Hyperlegible"

    def glyph(text: str) -> bytes:
        image = Image.new("L", (40, 40))
        ImageDraw.Draw(image).text((4, 4), text, font=font, fill=255)
        return image.tobytes()

    missing = glyph("￿")  # the "no such letter" box
    for letter in "æøåÆØÅàèéìòù–":
        assert glyph(letter) != missing, letter
