from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Mark:
    x: int
    y: int
    colour_slot: int = 0


@dataclass(frozen=True)
class Cell:
    x: int
    y: int


@dataclass(frozen=True)
class BackstitchKey:
    start_x: int
    start_y: int
    end_x: int
    end_y: int

    @classmethod
    def between(cls, start_x: int, start_y: int, end_x: int, end_y: int) -> "BackstitchKey":
        start = (start_x, start_y)
        end = (end_x, end_y)
        if end < start:
            start, end = end, start
        return cls(start[0], start[1], end[0], end[1])


@dataclass(frozen=True)
class Backstitch:
    start_x: int
    start_y: int
    end_x: int
    end_y: int
    colour_slot: int = 0

    @property
    def key(self) -> BackstitchKey:
        return BackstitchKey.between(self.start_x, self.start_y, self.end_x, self.end_y)


@dataclass
class RepeatOverride:
    """Changes applied to every unit along one outer repeat row or column."""

    removed_cells: list[Cell] = field(default_factory=list)
    added_marks: list[Mark] = field(default_factory=list)
    removed_backstitches: list[BackstitchKey] = field(default_factory=list)
    added_backstitches: list[Backstitch] = field(default_factory=list)
    extension: int = 0

    def set_mark(self, x: int, y: int, colour_slot: int) -> None:
        self.removed_cells = [cell for cell in self.removed_cells if not (cell.x == x and cell.y == y)]
        self.added_marks = [mark for mark in self.added_marks if not (mark.x == x and mark.y == y)]
        self.added_marks.append(Mark(x, y, colour_slot))

    def remove_added_mark(self, x: int, y: int) -> None:
        self.added_marks = [mark for mark in self.added_marks if not (mark.x == x and mark.y == y)]

    def hide_cell(self, x: int, y: int) -> None:
        self.remove_added_mark(x, y)
        if Cell(x, y) not in self.removed_cells:
            self.removed_cells.append(Cell(x, y))

    def is_empty(self) -> bool:
        return (
            not self.removed_cells
            and not self.added_marks
            and not self.removed_backstitches
            and not self.added_backstitches
            and self.extension == 0
        )

    def set_backstitch(self, backstitch: Backstitch) -> None:
        key = backstitch.key
        self.removed_backstitches = [item for item in self.removed_backstitches if item != key]
        self.added_backstitches = [item for item in self.added_backstitches if item.key != key]
        self.added_backstitches.append(backstitch)

    def hide_backstitch(self, key: BackstitchKey) -> None:
        self.added_backstitches = [item for item in self.added_backstitches if item.key != key]
        if key not in self.removed_backstitches:
            self.removed_backstitches.append(key)

    def restore_backstitch(self, key: BackstitchKey) -> None:
        self.removed_backstitches = [item for item in self.removed_backstitches if item != key]
        self.added_backstitches = [item for item in self.added_backstitches if item.key != key]


@dataclass
class PatternDocument:
    format_version: int = 4
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
    palette: list[str] = field(
        default_factory=lambda: ["#b1172b", "#2d7d32", "#f2c84b", "#1b1b1b"]
    )
    palette_sequences: list[list[str]] = field(default_factory=list)
    symmetry: list[str] = field(default_factory=lambda: ["identity"])
    motif: list[Mark] = field(default_factory=list)
    backstitches: list[Backstitch] = field(default_factory=list)
    top_repeat_override: RepeatOverride | None = None
    bottom_repeat_override: RepeatOverride | None = None
    left_repeat_override: RepeatOverride | None = None
    right_repeat_override: RepeatOverride | None = None

    def validate(self) -> None:
        if self.unit_width < 1 or self.unit_height < 1:
            raise ValueError("Unit dimensions must be positive")
        if self.repeats_x < 1 or self.repeats_y < 1:
            raise ValueError("Repeat counts must be positive")
        if not self.palette:
            raise ValueError("The palette must contain at least one colour")
        for mark in self.motif:
            if not (0 <= mark.x < self.unit_width and 0 <= mark.y < self.unit_height):
                raise ValueError(f"Mark outside recurring unit: {mark}")
        for backstitch in self.backstitches:
            self._validate_backstitch(backstitch, 0, self.unit_width, 0, self.unit_height)
        for edge in ("top", "bottom", "left", "right"):
            self._validate_repeat_override(getattr(self, f"{edge}_repeat_override"), edge)

    def _validate_repeat_override(self, override: RepeatOverride | None, edge: str) -> None:
        if override is None:
            return
        if override.extension < 0:
            raise ValueError(f"{edge.capitalize()} repeat extension cannot be negative")
        for cell in override.removed_cells:
            if not (0 <= cell.x < self.unit_width and 0 <= cell.y < self.unit_height):
                raise ValueError(f"Removed cell outside recurring unit: {cell}")
        minimum_x = -override.extension if edge == "left" else 0
        maximum_x = self.unit_width + override.extension - 1 if edge == "right" else self.unit_width - 1
        minimum_y = -override.extension if edge == "top" else 0
        maximum_y = self.unit_height + override.extension - 1 if edge == "bottom" else self.unit_height - 1
        for mark in override.added_marks:
            if not (minimum_x <= mark.x <= maximum_x and minimum_y <= mark.y <= maximum_y):
                raise ValueError(f"Added mark outside {edge} repeat editor: {mark}")
        for key in override.removed_backstitches:
            self._validate_backstitch(key, 0, self.unit_width, 0, self.unit_height)
        for backstitch in override.added_backstitches:
            self._validate_backstitch(
                backstitch,
                minimum_x,
                maximum_x + 1,
                minimum_y,
                maximum_y + 1,
            )

    @staticmethod
    def _validate_backstitch(
        backstitch: Backstitch | BackstitchKey,
        minimum_x: int,
        maximum_x: int,
        minimum_y: int,
        maximum_y: int,
    ) -> None:
        if (backstitch.start_x, backstitch.start_y) == (backstitch.end_x, backstitch.end_y):
            raise ValueError("Backstitch endpoints must be different")
        for x, y in (
            (backstitch.start_x, backstitch.start_y),
            (backstitch.end_x, backstitch.end_y),
        ):
            if not (minimum_x <= x <= maximum_x and minimum_y <= y <= maximum_y):
                raise ValueError(f"Backstitch endpoint outside editor: {(x, y)}")

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

    def set_backstitch(self, backstitch: Backstitch) -> None:
        self.backstitches = [item for item in self.backstitches if item.key != backstitch.key]
        self.backstitches.append(backstitch)

    def erase_backstitch(self, key: BackstitchKey) -> None:
        self.backstitches = [item for item in self.backstitches if item.key != key]

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        if not result.get("palette_sequences"):
            result["palette_sequences"] = [[colour] for colour in self.palette]
        # Keep JSON canonical: palette is derived from palette_sequences.
        if "palette" in result:
            del result["palette"]
        result["motif"] = [asdict(mark) for mark in self.motif]
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PatternDocument":
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

        palette = [row[0] for row in palette_sequences]

        def parse_override(value: object) -> RepeatOverride | None:
            if value is None:
                return None
            if not isinstance(value, dict):
                raise ValueError("Repeat overrides must be JSON objects")
            return RepeatOverride(
                removed_cells=[
                    Cell(int(item["x"]), int(item["y"]))
                    for item in value.get("removed_cells", [])
                ],
                added_marks=[
                    Mark(int(item["x"]), int(item["y"]), int(item.get("colour_slot", 0)))
                    for item in value.get("added_marks", [])
                ],
                removed_backstitches=[
                    BackstitchKey.between(
                        int(item["start_x"]),
                        int(item["start_y"]),
                        int(item["end_x"]),
                        int(item["end_y"]),
                    )
                    for item in value.get("removed_backstitches", [])
                ],
                added_backstitches=[
                    Backstitch(
                        int(item["start_x"]),
                        int(item["start_y"]),
                        int(item["end_x"]),
                        int(item["end_y"]),
                        int(item.get("colour_slot", 0)),
                    )
                    for item in value.get("added_backstitches", [])
                ],
                extension=int(value.get("extension", 0)),
            )

        document = cls(
            format_version=4,
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
            palette=palette,
            palette_sequences=palette_sequences,
            symmetry=[str(value) for value in data.get("symmetry", ["identity"])],
            motif=[
                Mark(int(item["x"]), int(item["y"]), int(item.get("colour_slot", 0)))
                for item in data.get("motif", [])
            ],
            backstitches=[
                Backstitch(
                    int(item["start_x"]),
                    int(item["start_y"]),
                    int(item["end_x"]),
                    int(item["end_y"]),
                    int(item.get("colour_slot", 0)),
                )
                for item in data.get("backstitches", [])
            ],
            top_repeat_override=parse_override(data.get("top_repeat_override")),
            bottom_repeat_override=parse_override(data.get("bottom_repeat_override")),
            left_repeat_override=parse_override(data.get("left_repeat_override")),
            right_repeat_override=parse_override(data.get("right_repeat_override")),
        )
        document.validate()
        return document
