"""Command layer with undo/redo for any user interface.

An ``Editor`` owns the current ``PatternDocument``. A UI calls its methods for
every change and reads ``editor.document`` to draw. Undo is snapshot based: the
document is copied before each change, and changes that leave the document
equal to its previous state do not create an undo step.
"""

from __future__ import annotations

import copy
from collections.abc import Callable, Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass

from kvale.core import editing
from kvale.core.editing import Axis, Edge, Target
from kvale.core.model import PatternDocument


@dataclass(frozen=True)
class EditResult:
    changed: bool
    # Square-only symmetry operations switched off because the unit is not square.
    removed_symmetry: tuple[str, ...] = ()


class Editor:
    def __init__(self, document: PatternDocument | None = None, history_limit: int = 200) -> None:
        self._document = document if document is not None else PatternDocument()
        self.history_limit = history_limit
        self._undo_stack: list[PatternDocument] = []
        self._redo_stack: list[PatternDocument] = []
        self._batch_depth = 0
        self._batch_start: PatternDocument | None = None

    @property
    def document(self) -> PatternDocument:
        """The current document. Undo and redo replace this object, so do not keep it."""
        return self._document

    def load(self, document: PatternDocument) -> None:
        """Start editing another document and clear the history."""
        if self._batch_depth:
            raise RuntimeError("Cannot load a document while a batch is open")
        self._document = document
        self._undo_stack.clear()
        self._redo_stack.clear()

    # History -----------------------------------------------------------

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def undo(self) -> bool:
        """Go back one step. Returns False when there is nothing to undo."""
        self._check_no_batch("undo")
        if not self._undo_stack:
            return False
        self._redo_stack.append(self._document)
        self._document = self._undo_stack.pop()
        return True

    def redo(self) -> bool:
        """Repeat the last undone step. Returns False when there is nothing to redo."""
        self._check_no_batch("redo")
        if not self._redo_stack:
            return False
        self._undo_stack.append(self._document)
        self._document = self._redo_stack.pop()
        return True

    def begin_batch(self) -> None:
        """Group the following edits into one undo step, e.g. for a drag-paint stroke.

        Batches can nest; the step is recorded when the outermost batch ends.
        """
        if self._batch_depth == 0:
            self._batch_start = copy.deepcopy(self._document)
        self._batch_depth += 1

    def end_batch(self) -> bool:
        """Close a batch. Returns True when the outermost batch changed the document."""
        if self._batch_depth == 0:
            raise RuntimeError("end_batch() called without begin_batch()")
        self._batch_depth -= 1
        if self._batch_depth:
            return False
        start = self._batch_start
        self._batch_start = None
        if start is None or start == self._document:
            return False
        self._record(start)
        return True

    @contextmanager
    def batch(self) -> Iterator[None]:
        """Context manager form of begin_batch()/end_batch()."""
        self.begin_batch()
        try:
            yield
        finally:
            self.end_batch()

    def _check_no_batch(self, action: str) -> None:
        if self._batch_depth:
            raise RuntimeError(f"Cannot {action} while a batch is open")

    def _record(self, previous: PatternDocument) -> None:
        self._undo_stack.append(previous)
        if len(self._undo_stack) > self.history_limit:
            del self._undo_stack[0]
        self._redo_stack.clear()

    def _apply(self, edit: Callable[[PatternDocument], Sequence[str] | None]) -> EditResult:
        before = copy.deepcopy(self._document)
        removed = edit(self._document) or []
        changed = self._document != before
        if changed and self._batch_depth == 0:
            self._record(before)
        return EditResult(changed, tuple(removed))

    # Marks -------------------------------------------------------------

    def paint(self, x: int, y: int, colour_slot: int, target: Target = "unit") -> EditResult:
        """Paint a cell of the unit or of an end piece.

        In the unit, painting a generated copy recolours its source mark. See
        ``editing.paint_cell`` and ``editing.paint_end_piece_cell``.
        """

        def edit(document: PatternDocument) -> None:
            if target == "unit":
                editing.paint_cell(document, x, y, colour_slot)
            else:
                editing.paint_end_piece_cell(document, target, x, y, colour_slot)

        return self._apply(edit)

    def erase(self, x: int, y: int, target: Target = "unit") -> EditResult:
        """Erase a cell of the unit (with all its copies) or hide/remove one in an end piece."""

        def edit(document: PatternDocument) -> None:
            if target == "unit":
                editing.erase_cell(document, x, y)
            else:
                editing.erase_end_piece_cell(document, target, x, y)

        return self._apply(edit)

    # Backstitches ------------------------------------------------------

    def add_backstitch(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
        colour_slot: int,
        target: Target = "unit",
    ) -> EditResult:
        """Add a backstitch between two grid intersections of the unit or an end piece."""

        def edit(document: PatternDocument) -> None:
            if target == "unit":
                editing.add_backstitch(document, start, end, colour_slot)
            else:
                editing.add_end_piece_backstitch(document, target, start, end, colour_slot)

        return self._apply(edit)

    def erase_backstitch_near(self, x: float, y: float, target: Target = "unit") -> EditResult:
        """Erase the backstitch nearest to grid point (x, y); see ``editing.erase_backstitch_near``."""

        def edit(document: PatternDocument) -> None:
            editing.erase_backstitch_near(document, x, y, target)

        return self._apply(edit)

    # End pieces --------------------------------------------------------

    def set_end_piece_extension(self, edge: Edge, extension: int) -> EditResult:
        """Set the extra rows/columns of an end piece beyond the unit."""

        def edit(document: PatternDocument) -> None:
            editing.set_end_piece_extension(document, edge, extension)

        return self._apply(edit)

    def reset_end_piece(self, edge: Edge) -> EditResult:
        """Remove every change an end piece makes."""

        def edit(document: PatternDocument) -> None:
            editing.reset_end_piece(document, edge)

        return self._apply(edit)

    # Grid --------------------------------------------------------------

    def change_grid_line(self, axis: Axis, index: int, *, insertion: bool) -> EditResult:
        """Insert or remove a row/column and its symmetric partners; see ``editing.change_grid_line``."""
        return self._apply(
            lambda document: editing.change_grid_line(document, axis, index, insertion=insertion)
        )

    def insert_column(self, index: int) -> EditResult:
        return self.change_grid_line("column", index, insertion=True)

    def remove_column(self, index: int) -> EditResult:
        return self.change_grid_line("column", index, insertion=False)

    def insert_row(self, index: int) -> EditResult:
        return self.change_grid_line("row", index, insertion=True)

    def remove_row(self, index: int) -> EditResult:
        return self.change_grid_line("row", index, insertion=False)

    def set_grid(
        self,
        *,
        unit_width: int | None = None,
        unit_height: int | None = None,
        repeats_x: int | None = None,
        repeats_y: int | None = None,
        repeat_left_column: bool | None = None,
        repeat_right_column: bool | None = None,
        repeat_top_row: bool | None = None,
        repeat_bottom_row: bool | None = None,
    ) -> EditResult:
        """Change grid settings in one undo step. Arguments left as None are kept.

        The unit is resized from its top-left corner; see ``editing.resize_unit``.
        When no setting changes, the document is left exactly as it is.
        """

        def edit(document: PatternDocument) -> list[str]:
            requested = (
                max(1, document.unit_width if unit_width is None else unit_width),
                max(1, document.unit_height if unit_height is None else unit_height),
                max(1, document.repeats_x if repeats_x is None else repeats_x),
                max(1, document.repeats_y if repeats_y is None else repeats_y),
                document.repeat_left_column if repeat_left_column is None else repeat_left_column,
                document.repeat_right_column if repeat_right_column is None else repeat_right_column,
                document.repeat_top_row if repeat_top_row is None else repeat_top_row,
                document.repeat_bottom_row if repeat_bottom_row is None else repeat_bottom_row,
            )
            current = (
                document.unit_width,
                document.unit_height,
                document.repeats_x,
                document.repeats_y,
                document.repeat_left_column,
                document.repeat_right_column,
                document.repeat_top_row,
                document.repeat_bottom_row,
            )
            if requested == current:
                return []
            editing.set_repeats(
                document,
                document.repeats_x if repeats_x is None else repeats_x,
                document.repeats_y if repeats_y is None else repeats_y,
            )
            if repeat_left_column is not None:
                document.repeat_left_column = repeat_left_column
            if repeat_right_column is not None:
                document.repeat_right_column = repeat_right_column
            if repeat_top_row is not None:
                document.repeat_top_row = repeat_top_row
            if repeat_bottom_row is not None:
                document.repeat_bottom_row = repeat_bottom_row
            return editing.resize_unit(
                document,
                document.unit_width if unit_width is None else unit_width,
                document.unit_height if unit_height is None else unit_height,
            )

        return self._apply(edit)

    def set_symmetry(self, operations: Iterable[str]) -> EditResult:
        """Select symmetry operations; see ``kvale.core.symmetry.normalise_symmetry``."""
        selected = list(operations)
        return self._apply(lambda document: editing.set_symmetry(document, selected))

    # Colours -----------------------------------------------------------

    def add_colour(self, colour: str) -> EditResult:
        """Add a colour slot at the end of the palette."""

        def edit(document: PatternDocument) -> None:
            editing.add_palette_colour(document, colour)

        return self._apply(edit)

    def set_colour_sequence(self, index: int, sequence: Sequence[str]) -> EditResult:
        """Replace the colour sequence of one slot."""
        return self._apply(lambda document: editing.set_palette_sequence(document, index, sequence))

    def set_use_palette_sequence(self, enabled: bool) -> EditResult:
        def edit(document: PatternDocument) -> None:
            document.use_palette_sequence = enabled

        return self._apply(edit)

    def set_background(self, colour: str) -> EditResult:
        def edit(document: PatternDocument) -> None:
            document.background = colour

        return self._apply(edit)
