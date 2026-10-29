"""Draw the app icons in ``web/icons/`` from the logo mark in the top bar.

    python tools/make_icons.py

The logo (``#i-logo`` in ``web/index.html``) is a rounded square with a cross
stitch in it, drawn in the accent colour. The icons put it on the fabric colour:

- ``icon.svg``, ``icon-192.png``, ``icon-512.png``: the logo filling the icon;
- ``maskable-192.png``, ``maskable-512.png``: the fabric fills the whole square
  and the logo stays inside the safe zone, for launchers that crop to a shape;
- ``apple-touch-icon.png`` (180 px): like maskable, as iOS adds its own corners.

The colours are the light-theme tokens ``--surface`` and ``--accent``. The PNGs
are committed; run this again only when the logo or the colours change.
"""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "icons"
TOKENS = ROOT / "web" / "tokens.css"
LOGO_BOX = 34  # the logo's viewBox is 0 0 34 34
SUPERSAMPLE = 4


def token(name: str) -> str:
    """The first (light theme) value of a colour token in tokens.css."""
    match = re.search(rf"--{name}:\s*(#[0-9a-fA-F]{{6}})", TOKENS.read_text(encoding="utf-8"))
    if not match:
        raise SystemExit(f"--{name} not found in {TOKENS}")
    return match.group(1).lower()


def logo_svg(fabric: str, accent: str) -> str:
    """The logo on a rounded fabric-coloured square, as a standalone SVG."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 34 34">'
        f'<rect x="1" y="1" width="32" height="32" rx="7" fill="{fabric}" '
        f'stroke="{accent}" stroke-width="2"/>'
        f'<path d="M9 9l16 16M25 9L9 25" stroke="{accent}" stroke-width="3.2" '
        'stroke-linecap="round"/></svg>\n'
    )


def draw_logo(size: int, fabric: str, accent: str, *, maskable: bool) -> Image.Image:
    big = size * SUPERSAMPLE
    image = Image.new("RGBA", (big, big), fabric if maskable else (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    # Maskable icons keep the logo in the middle 60 % (the safe zone is a circle of 80 %).
    logo = big * (0.6 if maskable else 1.0)
    offset = (big - logo) / 2
    unit = logo / LOGO_BOX

    def at(value: float) -> float:
        return offset + value * unit

    stroke = 2 * unit
    draw.rounded_rectangle(
        (at(1) - stroke / 2, at(1) - stroke / 2, at(33) + stroke / 2, at(33) + stroke / 2),
        radius=(7 + 1) * unit,
        fill=accent,
    )
    draw.rounded_rectangle(
        (at(1) + stroke / 2, at(1) + stroke / 2, at(33) - stroke / 2, at(33) - stroke / 2),
        radius=(7 - 1) * unit,
        fill=fabric,
    )
    width = 3.2 * unit
    for start, end in (((9, 9), (25, 25)), ((25, 9), (9, 25))):
        draw.line(
            (at(start[0]), at(start[1]), at(end[0]), at(end[1])), fill=accent, width=round(width)
        )
        for x, y in (start, end):
            r = width / 2
            draw.ellipse((at(x) - r, at(y) - r, at(x) + r, at(y) + r), fill=accent)
    return image.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    fabric, accent = token("surface"), token("accent")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "icon.svg").write_text(logo_svg(fabric, accent), encoding="utf-8")
    images = {
        "icon-192.png": draw_logo(192, fabric, accent, maskable=False),
        "icon-512.png": draw_logo(512, fabric, accent, maskable=False),
        "maskable-192.png": draw_logo(192, fabric, accent, maskable=True),
        "maskable-512.png": draw_logo(512, fabric, accent, maskable=True),
        "apple-touch-icon.png": draw_logo(180, fabric, accent, maskable=True).convert("RGB"),
    }
    for name, image in images.items():
        image.save(OUT / name, optimize=True)
        print(f"Wrote {OUT / name}")


if __name__ == "__main__":
    main()
