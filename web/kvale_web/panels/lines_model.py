"""The rows and columns dialog without the DOM: what the choice means.

``LinesChoice`` is what the person picked (add or remove, and where);
``lines_effect`` works out which rows and columns that changes once the
symmetry takes its partners along, whether it is allowed, and the new size.
Runs in plain CPython.
"""

from __future__ import annotations

from dataclasses import dataclass

from kvale.core.editing import (
    Axis,
    GridPlace,
    grid_line_for_place,
    grid_line_orbit,
    max_line_number,
)
from kvale.core.model import PatternDocument

# The "Where?" buttons, in the order of the design, with their i18n keys.
PLACES: tuple[tuple[GridPlace, str], ...] = (
    ("top_row", "lines.place.top"),
    ("bottom_row", "lines.place.bottom"),
    ("first_column", "lines.place.first"),
    ("last_column", "lines.place.last"),
    ("row", "lines.place.row"),
    ("column", "lines.place.col"),
)
NUMBERED: tuple[GridPlace, ...] = ("row", "column")


@dataclass
class LinesChoice:
    insertion: bool = True
    place: GridPlace = "bottom_row"
    # 1-based row/column number, for the places "row" and "column".
    number: int = 1

    @property
    def numbered(self) -> bool:
        return self.place in NUMBERED

    def max_number(self, document: PatternDocument) -> int:
        """Highest number offered for a numbered place (inserting may add after the last)."""
        axis: Axis = "column" if self.place == "column" else "row"
        return max_line_number(document, axis, insertion=self.insertion)

    def clamp(self, document: PatternDocument) -> None:
        self.number = max(1, min(self.max_number(document), self.number))

    def line(self, document: PatternDocument) -> tuple[Axis, int]:
        """``(axis, index)`` for ``Editor.change_grid_line``."""
        self.clamp(document)
        return grid_line_for_place(document, self.place, insertion=self.insertion, number=self.number)


@dataclass(frozen=True)
class LinesEffect:
    insertion: bool
    # For insertion: the gaps where new lines go (0 = before the first);
    # for removal: the lines that go. 0-based, sorted.
    columns: tuple[int, ...]
    rows: tuple[int, ...]
    allowed: bool
    new_width: int
    new_height: int

    @property
    def count(self) -> int:
        return len(self.columns) + len(self.rows)

    def labels(self) -> list[tuple[str, int]]:
        """(i18n key, 1-based number) for each changed line: rows first, then columns.

        New lines are numbered as they will be after the insertion.
        """
        if self.insertion:
            rows = [gap + k + 1 for k, gap in enumerate(self.rows)]
            columns = [gap + k + 1 for k, gap in enumerate(self.columns)]
            return [("grid.newRowN", n) for n in rows] + [("grid.newColN", n) for n in columns]
        return [("grid.rowN", y + 1) for y in self.rows] + [("grid.colN", x + 1) for x in self.columns]


def lines_effect(document: PatternDocument, choice: LinesChoice) -> LinesEffect:
    axis, index = choice.line(document)
    orbit = grid_line_orbit(document, axis, index, insertion=choice.insertion)
    columns = tuple(sorted(value for kind, value in orbit if kind == "column"))
    rows = tuple(sorted(value for kind, value in orbit if kind == "row"))
    sign = 1 if choice.insertion else -1
    width = document.unit_width + sign * len(columns)
    height = document.unit_height + sign * len(rows)
    return LinesEffect(choice.insertion, columns, rows, width >= 1 and height >= 1, width, height)
