"""DMC embroidery floss colours.

The colours in dmc_palette.json are screen approximations of the DMC
stranded cotton range; a physical colour card is needed when the exact
thread matters.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources


@dataclass(frozen=True)
class DmcColour:
    number: str
    name: str
    red: int
    green: int
    blue: int

    @property
    def hex_colour(self) -> str:
        return f"#{self.red:02x}{self.green:02x}{self.blue:02x}"


@lru_cache(maxsize=1)
def load_dmc_colours() -> tuple[DmcColour, ...]:
    """Load the bundled DMC screen-colour approximations, in colour-card order."""
    source = resources.files("kvale.core").joinpath("dmc_palette.json")
    records = json.loads(source.read_text(encoding="utf-8"))
    return tuple(
        DmcColour(
            number=str(record["floss"]),
            name=str(record["description"]),
            red=int(record["r"]),
            green=int(record["g"]),
            blue=int(record["b"]),
        )
        for record in records
    )


def filter_dmc_colours(query: str) -> tuple[DmcColour, ...]:
    """Colours whose number or name contains every word of ``query`` (case-insensitive)."""
    words = query.casefold().split()
    if not words:
        return load_dmc_colours()
    return tuple(
        colour
        for colour in load_dmc_colours()
        if all(word in colour.number.casefold() or word in colour.name.casefold() for word in words)
    )


def find_dmc_colour(hex_colour: str) -> DmcColour | None:
    """The first DMC colour with this screen colour (e.g. "#ffe2e2"), if any."""
    target = hex_colour.casefold()
    return next(
        (colour for colour in load_dmc_colours() if colour.hex_colour.casefold() == target),
        None,
    )
