"""Thread brands and thread colours: a colour is a (brand, code) pair or an own colour.

A thread is named by a *thread reference*, ``"<brand id>:<code>"``, for
example ``"dmc:321"``. A colour with no reference (``None``) is an own colour,
known only by its screen colour. Every code a UI shows names its brand, as
"DMC 321" (see ``display_code``).

Brands are data: ``BRANDS`` lists them, and a brand with a ``catalogue`` reads
its threads from that package data file (the format of ``dmc_palette.json``:
a list of ``{"floss", "description", "r", "g", "b"}``). Adding a brand means
adding its catalogue file and one ``ThreadBrand`` entry. A brand without a
catalogue is shown as "coming later".

Documents store the references in ``PatternDocument.palette_threads``, one per
colour of ``palette_sequences``. Files from before that field have none; for
them ``slot_threads`` reads a colour that matches a DMC screen colour as that
DMC thread and anything else as an own colour.

The screen colours are approximations; a physical shade card is needed when
the exact thread matters.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from importlib import resources
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kvale.core.model import PatternDocument


@dataclass(frozen=True)
class ThreadBrand:
    id: str
    name: str
    # Package data file in kvale.core with the brand's threads; None = coming later.
    catalogue: str | None = None

    @property
    def available(self) -> bool:
        return self.catalogue is not None


@dataclass(frozen=True)
class Thread:
    brand: str
    code: str
    name: str
    hex_colour: str

    @property
    def ref(self) -> str:
        return thread_ref(self.brand, self.code)


# In the order a UI lists them. The first available brand is the default.
BRANDS: tuple[ThreadBrand, ...] = (
    ThreadBrand("dmc", "DMC", "dmc_palette.json"),
    ThreadBrand("anchor", "Anchor"),
    ThreadBrand("madeira", "Madeira"),
)
DEFAULT_BRAND = "dmc"

# Colour families offered as filters, in display order ("all" = no filter).
FAMILIES = ("all", "red", "pink", "orange", "yellow", "green", "blue", "purple", "brown", "neutral")
# A representative colour for each family's filter chip.
FAMILY_CHIP = {
    "red": "#c72b3b",
    "pink": "#e48ea5",
    "orange": "#ff8b00",
    "yellow": "#ffc840",
    "green": "#3f8f29",
    "blue": "#253b73",
    "purple": "#633666",
    "brown": "#7a451f",
    "neutral": "#8c8c8c",
}


def get_brand(brand_id: str) -> ThreadBrand | None:
    return next((brand for brand in BRANDS if brand.id == brand_id), None)


def brand_name(brand_id: str) -> str:
    """Display name of a brand; an unknown id is shown in capitals."""
    brand = get_brand(brand_id)
    return brand.name if brand else brand_id.upper()


def thread_ref(brand_id: str, code: str) -> str:
    return f"{brand_id}:{code}"


def parse_thread_ref(ref: str) -> tuple[str, str] | None:
    """``"dmc:321"`` -> ``("dmc", "321")``; None for anything else."""
    brand_id, sep, code = ref.partition(":")
    if not sep or not brand_id or not code:
        return None
    return brand_id, code


def display_code(ref: str) -> tuple[str, str] | None:
    """(brand name, code) to show for a reference, e.g. ("DMC", "321")."""
    parsed = parse_thread_ref(ref)
    if parsed is None:
        return None
    return brand_name(parsed[0]), parsed[1]


@cache
def brand_threads(brand_id: str) -> tuple[Thread, ...]:
    """The threads of a brand, in shade-card order (empty when it has no catalogue)."""
    brand = get_brand(brand_id)
    if brand is None or brand.catalogue is None:
        return ()
    source = resources.files("kvale.core").joinpath(brand.catalogue)
    records = json.loads(source.read_text(encoding="utf-8"))
    return tuple(
        Thread(
            brand=brand.id,
            code=str(record["floss"]),
            # The bundled DMC card has "?" for a lost hyphen ("Orange?Red Bright").
            name=str(record["description"]).replace("?", "-"),
            hex_colour=f"#{int(record['r']):02x}{int(record['g']):02x}{int(record['b']):02x}",
        )
        for record in records
    )


@cache
def _by_code(brand_id: str) -> dict[str, Thread]:
    return {thread.code.casefold(): thread for thread in brand_threads(brand_id)}


@cache
def _by_hex(brand_id: str) -> dict[str, Thread]:
    found: dict[str, Thread] = {}
    for thread in brand_threads(brand_id):
        found.setdefault(thread.hex_colour, thread)
    return found


def find_thread(ref: str | None) -> Thread | None:
    """The catalogue thread for a reference, or None (own colour, unknown thread)."""
    if not ref:
        return None
    parsed = parse_thread_ref(ref)
    if parsed is None:
        return None
    return _by_code(parsed[0]).get(parsed[1].casefold())


def infer_thread(hex_colour: str, brand_id: str = DEFAULT_BRAND) -> str | None:
    """The reference of the thread with exactly this screen colour, if any.

    Used for files saved before thread references were stored.
    """
    thread = _by_hex(brand_id).get(hex_colour.strip().casefold())
    return thread.ref if thread else None


def colour_family(hex_colour: str) -> str:
    """The family filter ("red", "neutral" ...) a screen colour belongs to."""
    value = int(hex_colour.lstrip("#")[:6], 16)
    red, green, blue = ((value >> 16) & 255) / 255, ((value >> 8) & 255) / 255, (value & 255) / 255
    high, low = max(red, green, blue), min(red, green, blue)
    lightness = (high + low) / 2
    spread = high - low
    saturation = 0.0 if spread == 0 else spread / (1 - abs(2 * lightness - 1))
    hue = 0.0
    if spread:
        if high == red:
            hue = ((green - blue) / spread) % 6
        elif high == green:
            hue = (blue - red) / spread + 2
        else:
            hue = (red - green) / spread + 4
        hue *= 60
    if saturation < 0.14 or lightness > 0.94 or lightness < 0.08:
        return "neutral"
    if (hue < 50 and lightness < 0.42 and saturation < 0.75) or (20 <= hue < 50 and saturation < 0.38):
        return "brown"
    if hue < 12 or hue >= 345:
        return "pink" if lightness > 0.72 else "red"
    for limit, family in ((42, "orange"), (68, "yellow"), (170, "green"), (255, "blue"), (300, "purple")):
        if hue < limit:
            return family
    return "pink"


def search_threads(brand_id: str, query: str = "", family: str = "all") -> tuple[Thread, ...]:
    """Threads of a brand whose code or name contains every word of ``query``.

    A leading brand name is ignored, so "DMC 321" finds the same as "321".
    ``family`` filters by ``colour_family`` ("all" keeps every family).
    """
    words = query.casefold().split()
    name = brand_name(brand_id).casefold()
    if words and words[0] == name:
        words = words[1:]
    elif words and words[0].startswith(name + "-"):
        words[0] = words[0][len(name) + 1 :]
    words = [word for word in words if word]
    return tuple(
        thread
        for thread in brand_threads(brand_id)
        if (family == "all" or colour_family(thread.hex_colour) == family)
        and all(word in thread.code.casefold() or word in thread.name.casefold() for word in words)
    )


def slot_threads(document: PatternDocument) -> list[list[str | None]]:
    """The thread reference of every colour, shaped like ``palette_sequences``.

    Without stored references (older files), colours matching a DMC screen
    colour are read as that DMC thread and the rest as own colours.
    """
    if document.palette_threads is not None:
        return [list(row) for row in document.palette_threads]
    return [[infer_thread(colour) for colour in sequence] for sequence in document.palette_sequences]


def threads_for(sequence: Sequence[str], refs: Sequence[str | None] | None) -> list[str | None]:
    """``refs`` checked against ``sequence``, or inferred from the colours when None."""
    if refs is None:
        return [infer_thread(colour) for colour in sequence]
    if len(refs) != len(sequence):
        raise ValueError("A thread reference is needed for every colour of the sequence")
    return [ref or None for ref in refs]
