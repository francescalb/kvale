"""Colours without the DOM: slot summaries, the colour dialog's draft sequence,
the thread picker's search, and the list of threads a pattern uses.

A colour is shown from its screen colour (hex) and its thread reference
("dmc:321", or None for an own colour; see ``kvale.core.threads``). Text is
made by the views with ``t()``; this module only hands them the parts, so it
runs (and is tested) in plain CPython.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from kvale.core.editing import END_PIECES, MAX_SEQUENCE_LENGTH, get_end_piece
from kvale.core.model import PatternDocument
from kvale.core.threads import (
    DEFAULT_BRAND,
    Thread,
    display_code,
    find_thread,
    get_brand,
    parse_thread_ref,
    search_threads,
    slot_threads,
)

# Threads offered as one-tap choices in the colour dialog (as in the design).
QUICK_THREADS = tuple(
    f"dmc:{code}"
    for code in (
        "498", "321", "815", "606", "740", "725", "3865", "Ecru", "3346",
        "699", "701", "336", "796", "550", "433", "310", "414", "B5200",
    )
)
# Repeats shown in the colour dialog's "how the colour changes along the band".
BAND_PREVIEW_REPEATS = 10
DARK_TEXT = "#1b1712"
LIGHT_TEXT = "#ffffff"


@dataclass(frozen=True)
class ColourInfo:
    """What a view needs to show one colour."""

    hex_colour: str
    ref: str | None = None
    # (brand name, code) for a thread, e.g. ("DMC", "321"); None for an own colour.
    code: tuple[str, str] | None = None
    # The thread's name as the brand publishes it; "" for an own colour.
    name: str = ""

    @property
    def is_thread(self) -> bool:
        return self.code is not None


def colour_info(hex_colour: str, ref: str | None) -> ColourInfo:
    if ref:
        code = display_code(ref)
        thread = find_thread(ref)
        if code is not None:
            return ColourInfo(hex_colour, ref, code, thread.name if thread else "")
    return ColourInfo(hex_colour)


def slot_colours(document: PatternDocument) -> list[list[ColourInfo]]:
    """Every slot's colours, shaped like ``palette_sequences``."""
    refs = slot_threads(document)
    return [
        [colour_info(colour, ref) for colour, ref in zip(sequence, row, strict=True)]
        for sequence, row in zip(document.palette_sequences, refs, strict=True)
    ]


def used_slots(document: PatternDocument) -> set[int]:
    """Colour slots that some cross stitch or backstitch uses (unit or end pieces)."""
    count = len(document.palette_sequences)
    slots = {mark.colour_slot % count for mark in document.motif}
    slots |= {stitch.colour_slot % count for stitch in document.backstitches}
    for piece in END_PIECES:
        override = get_end_piece(document, piece)
        if override is not None:
            slots |= {mark.colour_slot % count for mark in override.added_marks}
            slots |= {stitch.colour_slot % count for stitch in override.added_backstitches}
    return slots


def thread_rows(document: PatternDocument) -> list[ColourInfo]:
    """The threads (and own colours) the pattern's stitches use, each once, in slot order.

    With "change colour from repeat to repeat" off, only the first colour of
    each slot is used. For the list under the whole band and in the saved image.
    """
    seen: set[str] = set()
    rows: list[ColourInfo] = []
    used = used_slots(document)
    for slot, sequence in enumerate(slot_colours(document)):
        if slot not in used:
            continue
        for info in sequence if document.use_palette_sequence else sequence[:1]:
            key = info.ref or info.hex_colour.casefold()
            if key not in seen:
                seen.add(key)
                rows.append(info)
    return rows


def luminance(hex_colour: str) -> float:
    """Relative luminance (0 = black, 1 = white) of ``#rrggbb``."""
    value = int(hex_colour.lstrip("#")[:6], 16)
    channels: list[float] = []
    for shift in (16, 8, 0):
        channel = ((value >> shift) & 255) / 255
        channels.append(channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4)
    return float(0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2])


def text_colour_on(hex_colour: str) -> str:
    """Dark or light text, whichever reads better on ``hex_colour``."""
    return DARK_TEXT if luminance(hex_colour) > 0.35 else LIGHT_TEXT


_HEX = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_RGB = re.compile(r"^(?:rgb\s*\()?\s*(\d{1,3})\s*[,\s]\s*(\d{1,3})\s*[,\s]\s*(\d{1,3})\s*\)?$")


def parse_colour(text: str) -> str | None:
    """``#rrggbb`` from what a person types: "#c72b3b", "c72b3b", "#c23", "199, 43, 59"."""
    text = text.strip()
    match = _HEX.match(text)
    if match:
        digits = match.group(1).lower()
        if len(digits) == 3:
            digits = "".join(ch * 2 for ch in digits)
        return f"#{digits}"
    match = _RGB.match(text.lower())
    if match:
        values = [int(part) for part in match.groups()]
        if all(0 <= value <= 255 for value in values):
            return "#" + "".join(f"{value:02x}" for value in values)
    return None


def band_preview(colours: list[str], repeats: int, use_sequence: bool) -> list[str]:
    """The colour of each of the first repeats along the band."""
    count = max(1, min(repeats, BAND_PREVIEW_REPEATS))
    return [colours[index % len(colours)] if use_sequence else colours[0] for index in range(count)]


@dataclass
class ColourDraft:
    """The colour dialog's working copy of one slot, applied on "Apply"."""

    slot: int
    colours: list[str]
    refs: list[str | None]
    part: int = 0

    @classmethod
    def from_document(cls, document: PatternDocument, slot: int) -> ColourDraft:
        return cls(slot, list(document.palette_sequences[slot]), list(slot_threads(document)[slot]))

    def resize(self, length: int) -> None:
        """1 to 24 parts; new parts repeat the last colour."""
        length = max(1, min(MAX_SEQUENCE_LENGTH, length))
        while len(self.colours) < length:
            self.colours.append(self.colours[-1])
            self.refs.append(self.refs[-1])
        del self.colours[length:]
        del self.refs[length:]
        self.part = min(self.part, length - 1)

    def select(self, part: int) -> None:
        if 0 <= part < len(self.colours):
            self.part = part

    def set_colour(self, hex_colour: str, ref: str | None) -> None:
        """Give the selected part a thread (``ref``) or an own colour (None)."""
        self.colours[self.part] = hex_colour.lower()
        self.refs[self.part] = ref

    @property
    def current(self) -> ColourInfo:
        return colour_info(self.colours[self.part], self.refs[self.part])

    def infos(self) -> list[ColourInfo]:
        return [colour_info(c, r) for c, r in zip(self.colours, self.refs, strict=True)]


@dataclass
class PickerState:
    """The thread picker: brand, search words, colour family and the chosen thread."""

    brand: str = DEFAULT_BRAND
    query: str = ""
    family: str = "all"
    selected: str | None = None
    results: tuple[Thread, ...] = field(default=(), repr=False)

    def reset(self, current: str | None) -> None:
        """Start again, with ``current`` (a reference) chosen when it is a known thread."""
        parsed = parse_thread_ref(current) if current else None
        brand = get_brand(parsed[0]) if parsed else None
        self.brand = brand.id if brand and brand.available else DEFAULT_BRAND
        self.query = ""
        self.family = "all"
        self.selected = current if find_thread(current) else None
        self.search()

    def set_brand(self, brand_id: str) -> bool:
        brand = get_brand(brand_id)
        if brand is None or not brand.available or brand_id == self.brand:
            return False
        self.brand = brand_id
        self.search()
        return True

    def set_query(self, query: str) -> None:
        self.query = query
        self.search()

    def set_family(self, family: str) -> None:
        self.family = family
        self.search()

    def search(self) -> None:
        self.results = search_threads(self.brand, self.query, self.family)

    def move(self, step: int) -> None:
        """Choose the next (``step`` 1) or previous (-1) thread in the results.

        From no choice (or one not in the results), down starts at the first
        and up at the last. It stops at either end.
        """
        refs = [thread.ref for thread in self.results]
        if not refs:
            return
        if self.selected in refs:
            index = max(0, min(len(refs) - 1, refs.index(self.selected) + step))
        else:
            index = 0 if step > 0 else len(refs) - 1
        self.selected = refs[index]

    @property
    def enter_choice(self) -> str | None:
        """What Enter in the search box chooses: the chosen thread if it is in
        the results, else the only result, else nothing."""
        refs = [thread.ref for thread in self.results]
        if self.selected in refs:
            return self.selected
        return refs[0] if len(refs) == 1 else None

    @property
    def chosen(self) -> Thread | None:
        return find_thread(self.selected)
