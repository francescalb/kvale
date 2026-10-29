"""The rows and columns dialog (chunk 5; a stub for now).

Belongs here: ``<dialog id="lines-dialog">``: add or remove, where (top,
bottom, far left, far right, row/column number), the effect including the
lines symmetry takes too, and the resulting size (``lines.*``). Use
``Editor.change_grid_line`` and ``kvale.core.editing.grid_line_orbit`` /
``grid_line_for_place`` / ``can_remove_grid_line``.

Other chunks open it with ``open_lines_dialog()`` (chunk 4's ruler popover
"More options …", chunk 5's "Repeat and size" card).
"""

from __future__ import annotations

from kvale_web.dom import Element, by_id
from kvale_web.state import AppState

_dialog: LinesDialog | None = None


class LinesDialog:
    def __init__(self, state: AppState) -> None:
        global _dialog
        self.state = state
        self.dialog: Element = by_id("lines-dialog")
        _dialog = self

    def open(self) -> None:
        """Show the dialog (not built yet)."""


def open_lines_dialog() -> None:
    """Open the rows and columns dialog, if the panels are mounted."""
    if _dialog is not None:
        _dialog.open()
