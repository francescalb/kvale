"""Edit operations on a PatternDocument.

Every function changes the document in place and keeps it consistent: marks
stay inside the recurring unit and the symmetry rules from
``normalise_symmetry`` hold after any change to the unit size. Functions that
can switch off symmetry operations return the names of those operations so a
UI can tell the user. Use ``kvale.core.editor.Editor`` to get undo/redo.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from kvale.core.model import Mark, PatternDocument
from kvale.core.symmetry import expand_marks, normalise_symmetry

# Longest colour sequence a UI should offer for one slot.
MAX_SEQUENCE_LENGTH = 24


def find_source_mark(document: PatternDocument, x: int, y: int) -> Mark | None:
    """Find the stored mark responsible for a displayed cell in the unit.

    The cell may hold the stored mark itself or one of its symmetry-generated
    copies. When several marks reach the cell, the first in the motif wins.
    """
    for mark in document.motif:
        generated_marks = expand_marks(
            [mark],
            width=document.unit_width,
            height=document.unit_height,
            operations=document.symmetry,
        )
        for generated in generated_marks:
            if generated.x == x and generated.y == y:
                return mark
    return None


def _in_unit(document: PatternDocument, x: int, y: int) -> bool:
    return 0 <= x < document.unit_width and 0 <= y < document.unit_height


def paint_cell(document: PatternDocument, x: int, y: int, colour_slot: int) -> bool:
    """Paint a displayed cell with a colour slot.

    Painting a generated copy recolours the stored mark that generated it;
    painting an empty cell adds a new mark there. Returns False when the cell
    is outside the unit.
    """
    if not _in_unit(document, x, y):
        return False
    source_mark = find_source_mark(document, x, y)
    if source_mark is not None:
        x, y = source_mark.x, source_mark.y
    document.set_mark(x, y, colour_slot)
    return True


def erase_cell(document: PatternDocument, x: int, y: int) -> bool:
    """Erase the stored mark that produces a displayed cell.

    Erasing a generated copy removes the stored mark and with it all its
    copies. Returns False when there was nothing to erase.
    """
    if not _in_unit(document, x, y):
        return False
    source_mark = find_source_mark(document, x, y)
    if source_mark is None:
        return False
    document.erase_mark(source_mark.x, source_mark.y)
    return True


def set_symmetry(document: PatternDocument, operations: Iterable[str]) -> list[str]:
    """Set the symmetry operations, applying the rules in ``normalise_symmetry``.

    Returns the square-only operations that were removed.
    """
    document.symmetry, removed = normalise_symmetry(
        operations, document.unit_width, document.unit_height
    )
    return removed


def _enforce_symmetry_rules(document: PatternDocument) -> list[str]:
    return set_symmetry(document, document.symmetry)


def insert_column(document: PatternDocument, index: int) -> list[str]:
    """Insert an empty column before ``index`` (clamped to 0..unit_width)."""
    index = max(0, min(index, document.unit_width))
    document.unit_width += 1
    document.motif = [
        Mark(mark.x + 1, mark.y, mark.colour_slot) if mark.x >= index else mark
        for mark in document.motif
    ]
    return _enforce_symmetry_rules(document)


def remove_column(document: PatternDocument, index: int) -> list[str]:
    """Remove the column at ``index`` and its marks. A one-column unit is left as is."""
    if document.unit_width <= 1:
        return []
    index = max(0, min(index, document.unit_width - 1))
    document.unit_width -= 1
    document.motif = [
        Mark(mark.x - 1, mark.y, mark.colour_slot) if mark.x > index else mark
        for mark in document.motif
        if mark.x != index
    ]
    return _enforce_symmetry_rules(document)


def insert_row(document: PatternDocument, index: int) -> list[str]:
    """Insert an empty row before ``index`` (clamped to 0..unit_height)."""
    index = max(0, min(index, document.unit_height))
    document.unit_height += 1
    document.motif = [
        Mark(mark.x, mark.y + 1, mark.colour_slot) if mark.y >= index else mark
        for mark in document.motif
    ]
    return _enforce_symmetry_rules(document)


def remove_row(document: PatternDocument, index: int) -> list[str]:
    """Remove the row at ``index`` and its marks. A one-row unit is left as is."""
    if document.unit_height <= 1:
        return []
    index = max(0, min(index, document.unit_height - 1))
    document.unit_height -= 1
    document.motif = [
        Mark(mark.x, mark.y - 1, mark.colour_slot) if mark.y > index else mark
        for mark in document.motif
        if mark.y != index
    ]
    return _enforce_symmetry_rules(document)


def resize_unit(document: PatternDocument, width: int, height: int) -> list[str]:
    """Resize the unit from its top-left corner, dropping marks that fall outside.

    Sizes below 1 are raised to 1.
    """
    document.unit_width = max(1, width)
    document.unit_height = max(1, height)
    document.motif = [
        mark
        for mark in document.motif
        if mark.x < document.unit_width and mark.y < document.unit_height
    ]
    return _enforce_symmetry_rules(document)


def set_repeats(document: PatternDocument, repeats_x: int, repeats_y: int) -> None:
    """Set the number of repeats across and down. Counts below 1 are raised to 1."""
    document.repeats_x = max(1, repeats_x)
    document.repeats_y = max(1, repeats_y)


def add_palette_colour(document: PatternDocument, colour: str) -> int:
    """Add a colour slot with a one-colour sequence and return its index."""
    document.palette_sequences.append([colour])
    return len(document.palette_sequences) - 1


def set_palette_sequence(document: PatternDocument, index: int, sequence: Sequence[str]) -> None:
    """Replace the colour sequence of slot ``index``. The first colour is the base colour."""
    if not 0 <= index < len(document.palette_sequences):
        raise IndexError(f"No colour slot {index}")
    if not sequence:
        raise ValueError("A palette sequence must contain at least one colour")
    document.palette_sequences[index] = list(sequence)


def resize_sequence(sequence: Sequence[str], length: int) -> list[str]:
    """Return ``sequence`` cut or extended to ``length`` (at least 1) colours.

    New entries repeat the last colour.
    """
    if not sequence:
        raise ValueError("A palette sequence must contain at least one colour")
    length = max(1, length)
    result = list(sequence[:length])
    result.extend([sequence[-1]] * (length - len(result)))
    return result
