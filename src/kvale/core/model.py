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
    def between(cls, start_x: int, start_y: int, end_x: int, end_y: int) -> BackstitchKey:
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


# The four corners of the band and the two edges that meet at each one, as
# (row edge, column edge).
CORNER_EDGES: dict[str, tuple[str, str]] = {
    "top_left": ("top", "left"),
    "top_right": ("top", "right"),
    "bottom_left": ("bottom", "left"),
    "bottom_right": ("bottom", "right"),
}
# Format version written when a document has corner overrides (see to_dict).
CORNER_FORMAT_VERSION = 5


def edge_cell_bounds(width: int, height: int, edge: str, extension: int) -> tuple[int, int, int, int]:
    """Cell range ``(min_x, max_x, min_y, max_y)`` (inclusive) of an edge end piece.

    That is the unit plus ``extension`` cells beyond it on ``edge``'s side.
    """
    minimum_x = -extension if edge == "left" else 0
    maximum_x = width + extension - 1 if edge == "right" else width - 1
    minimum_y = -extension if edge == "top" else 0
    maximum_y = height + extension - 1 if edge == "bottom" else height - 1
    return minimum_x, maximum_x, minimum_y, maximum_y


def corner_cell_bounds(
    width: int, height: int, corner: str, row_extension: int, column_extension: int
) -> tuple[int, int, int, int]:
    """Cell range ``(min_x, max_x, min_y, max_y)`` (inclusive) of a corner end piece.

    A corner covers the unit, the extensions of both edges that meet there
    (``row_extension`` of the top/bottom edge, ``column_extension`` of the
    left/right edge) and the square where those extensions cross.
    """
    row_edge, column_edge = CORNER_EDGES[corner]
    minimum_x, maximum_x, _, _ = edge_cell_bounds(width, height, column_edge, column_extension)
    _, _, minimum_y, maximum_y = edge_cell_bounds(width, height, row_edge, row_extension)
    return minimum_x, maximum_x, minimum_y, maximum_y


@dataclass
class RepeatOverride:
    """Changes applied to every unit along one outer repeat row or column.

    The same class describes a corner end piece, which changes only the one
    corner unit. A corner has no extension of its own: it follows the
    extensions of its two edges, and its ``extension`` must stay 0.
    """

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
    # One list of colours per colour slot. The first colour is the slot's base
    # colour; the rest are used along the repeats when use_palette_sequence is on.
    palette_sequences: list[list[str]] = field(
        default_factory=lambda: [["#b1172b"], ["#2d7d32"], ["#f2c84b"], ["#1b1b1b"]]
    )
    symmetry: list[str] = field(default_factory=lambda: ["identity"])
    motif: list[Mark] = field(default_factory=list)
    backstitches: list[Backstitch] = field(default_factory=list)
    top_repeat_override: RepeatOverride | None = None
    bottom_repeat_override: RepeatOverride | None = None
    left_repeat_override: RepeatOverride | None = None
    right_repeat_override: RepeatOverride | None = None
    # Corner end pieces, applied after the edge end pieces to the corner unit only.
    top_left_repeat_override: RepeatOverride | None = None
    top_right_repeat_override: RepeatOverride | None = None
    bottom_left_repeat_override: RepeatOverride | None = None
    bottom_right_repeat_override: RepeatOverride | None = None
    # Thread reference ("dmc:321", see kvale.core.threads) of each colour in
    # palette_sequences, None for an own colour. None as a whole for files
    # saved before references were stored: see threads.slot_threads.
    palette_threads: list[list[str | None]] | None = None

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
        if self.palette_threads is not None and [len(row) for row in self.palette_threads] != [
            len(row) for row in self.palette_sequences
        ]:
            raise ValueError("palette_threads must have one entry per palette colour")
        for mark in self.motif:
            if not (0 <= mark.x < self.unit_width and 0 <= mark.y < self.unit_height):
                raise ValueError(f"Mark outside recurring unit: {mark}")
        for backstitch in self.backstitches:
            self._validate_backstitch(backstitch, 0, self.unit_width, 0, self.unit_height)
        for edge in ("top", "bottom", "left", "right"):
            self._validate_repeat_override(getattr(self, f"{edge}_repeat_override"), edge)
        for corner in CORNER_EDGES:
            self._validate_corner_override(getattr(self, f"{corner}_repeat_override"), corner)

    def extension_of(self, edge: str) -> int:
        """Extra rows/columns the end piece on ``edge`` adds (0 when it has none)."""
        override: RepeatOverride | None = getattr(self, f"{edge}_repeat_override")
        return override.extension if override else 0

    def corner_bounds(self, corner: str) -> tuple[int, int, int, int]:
        """Cell range ``(min_x, max_x, min_y, max_y)`` (inclusive) of a corner end piece."""
        row_edge, column_edge = CORNER_EDGES[corner]
        return corner_cell_bounds(
            self.unit_width,
            self.unit_height,
            corner,
            self.extension_of(row_edge),
            self.extension_of(column_edge),
        )

    def has_corner_overrides(self) -> bool:
        return any(getattr(self, f"{corner}_repeat_override") is not None for corner in CORNER_EDGES)

    def _validate_corner_override(self, override: RepeatOverride | None, corner: str) -> None:
        if override is None:
            return
        if override.extension != 0:
            raise ValueError(f"Corner {corner} cannot have its own extension")
        minimum_x, maximum_x, minimum_y, maximum_y = self.corner_bounds(corner)
        cells: list[Cell | Mark] = [*override.removed_cells, *override.added_marks]
        for item in cells:
            if not (minimum_x <= item.x <= maximum_x and minimum_y <= item.y <= maximum_y):
                raise ValueError(f"Cell outside {corner} corner editor: {item}")
        stitches: list[Backstitch | BackstitchKey] = [
            *override.removed_backstitches,
            *override.added_backstitches,
        ]
        for backstitch in stitches:
            self._validate_backstitch(backstitch, minimum_x, maximum_x + 1, minimum_y, maximum_y + 1)

    def _validate_repeat_override(self, override: RepeatOverride | None, edge: str) -> None:
        if override is None:
            return
        if override.extension < 0:
            raise ValueError(f"{edge.capitalize()} repeat extension cannot be negative")
        for cell in override.removed_cells:
            if not (0 <= cell.x < self.unit_width and 0 <= cell.y < self.unit_height):
                raise ValueError(f"Removed cell outside recurring unit: {cell}")
        minimum_x, maximum_x, minimum_y, maximum_y = edge_cell_bounds(
            self.unit_width, self.unit_height, edge, override.extension
        )
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
        # palette is derived from palette_sequences, so it is not stored.
        data = asdict(self)
        # Corner fields are only written when set, and only then is the file
        # marked as format_version 5, so documents without corners are saved
        # exactly as before. format_version on the document itself stays the
        # base version (4); it is not raised by loading a version 5 file.
        for corner in CORNER_EDGES:
            if data[f"{corner}_repeat_override"] is None:
                del data[f"{corner}_repeat_override"]
        # Thread references are only written when known, so older documents
        # are saved exactly as before. Readers that do not know the field
        # ignore it and still get every colour from palette_sequences.
        if data["palette_threads"] is None:
            del data["palette_threads"]
        if self.has_corner_overrides():
            data["format_version"] = max(self.format_version, CORNER_FORMAT_VERSION)
        return data

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

        palette_threads: list[list[str | None]] | None = None
        raw_threads = data.get("palette_threads")
        if raw_threads is not None:
            if not isinstance(raw_threads, list) or not all(isinstance(row, list) for row in raw_threads):
                raise ValueError("palette_threads must be a list of lists")
            palette_threads = [[str(ref) if ref else None for ref in row] for row in raw_threads]

        version = data.get("format_version")
        if version is not None and int(version) > CORNER_FORMAT_VERSION:
            raise ValueError(
                f"Pattern file has format_version {version}; this version of Kvale reads up to "
                f"{CORNER_FORMAT_VERSION}"
            )

        def parse_override(value: object) -> RepeatOverride | None:
            if value is None:
                return None
            if not isinstance(value, dict):
                # ValueError (not TypeError) so callers can handle all bad files the same way.
                raise ValueError("Repeat overrides must be JSON objects")  # noqa: TRY004
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
            top_left_repeat_override=parse_override(data.get("top_left_repeat_override")),
            top_right_repeat_override=parse_override(data.get("top_right_repeat_override")),
            bottom_left_repeat_override=parse_override(data.get("bottom_left_repeat_override")),
            bottom_right_repeat_override=parse_override(data.get("bottom_right_repeat_override")),
            palette_threads=palette_threads,
        )
        document.validate()
        return document
