from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Mark:
    x: int
    y: int
    colour_slot: int = 0


@dataclass
class PatternDocument:
    unit_width: int = 12
    unit_height: int = 12
    repeats_x: int = 6
    repeats_y: int = 2
    repeat_left_column: bool = True
    repeat_right_column: bool = True
    repeat_top_row: bool = True
    repeat_bottom_row: bool = True
    use_palette_sequence: bool = False
    background: str = "#ffffff"
    # One list of colours per colour slot. The first colour is the slot's base
    # colour; the rest are used along the repeats when use_palette_sequence is on.
    palette_sequences: list[list[str]] = field(
        default_factory=lambda: [["#b1172b"], ["#2d7d32"], ["#f2c84b"], ["#1b1b1b"]]
    )
    symmetry: list[str] = field(default_factory=lambda: ["identity"])
    motif: list[Mark] = field(default_factory=list)

    @property
    def palette(self) -> list[str]:
        """Base colour of each slot (read-only, derived from palette_sequences)."""
        return [sequence[0] for sequence in self.palette_sequences]

    def validate(self) -> None:
        if self.unit_width < 1 or self.unit_height < 1:
            raise ValueError("Unit dimensions must be positive")
        if self.repeats_x < 1 or self.repeats_y < 1:
            raise ValueError("Repeat counts must be positive")
        if not self.palette_sequences:
            raise ValueError("The palette must contain at least one colour")
        if not all(self.palette_sequences):
            raise ValueError("Each palette sequence must contain at least one colour")
        for mark in self.motif:
            if not (0 <= mark.x < self.unit_width and 0 <= mark.y < self.unit_height):
                raise ValueError(f"Mark outside recurring unit: {mark}")

    def toggle_mark(self, x: int, y: int, colour_slot: int) -> None:
        existing = next((m for m in self.motif if m.x == x and m.y == y), None)
        if existing is not None:
            self.motif.remove(existing)
        else:
            self.motif.append(Mark(x, y, colour_slot))

    def set_mark(self, x: int, y: int, colour_slot: int) -> None:
        self.motif = [m for m in self.motif if not (m.x == x and m.y == y)]
        self.motif.append(Mark(x, y, colour_slot))

    def erase_mark(self, x: int, y: int) -> None:
        self.motif = [m for m in self.motif if not (m.x == x and m.y == y)]

    def to_dict(self) -> dict[str, Any]:
        # palette is derived from palette_sequences, so it is not stored.
        result = asdict(self)
        result["motif"] = [asdict(mark) for mark in self.motif]
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PatternDocument:
        raw_sequences = data.get("palette_sequences")
        if not isinstance(raw_sequences, list) or not raw_sequences:
            raise ValueError("Pattern file must contain non-empty palette_sequences")

        palette_sequences: list[list[str]] = []
        for entry in raw_sequences:
            if not isinstance(entry, list) or not entry:
                raise ValueError("Each palette sequence must be a non-empty list")
            row = [str(value) for value in entry if str(value)]
            if not row:
                raise ValueError("Palette sequence entries must contain colours")
            palette_sequences.append(row)

        document = cls(
            unit_width=int(data.get("unit_width", 12)),
            unit_height=int(data.get("unit_height", 12)),
            repeats_x=int(data.get("repeats_x", 6)),
            repeats_y=int(data.get("repeats_y", 2)),
            repeat_left_column=bool(data.get("repeat_left_column", True)),
            repeat_right_column=bool(data.get("repeat_right_column", True)),
            repeat_top_row=bool(data.get("repeat_top_row", True)),
            repeat_bottom_row=bool(data.get("repeat_bottom_row", True)),
            use_palette_sequence=bool(data.get("use_palette_sequence", False)),
            background=str(data.get("background", "#ffffff")),
            palette_sequences=palette_sequences,
            symmetry=[str(value) for value in data.get("symmetry", ["identity"])],
            motif=[
                Mark(int(item["x"]), int(item["y"]), int(item.get("colour_slot", 0)))
                for item in data.get("motif", [])
            ],
        )
        document.validate()
        return document
