"""The colour slot dialog (chunk 5; a stub for now).

Belongs here: ``<dialog id="colour-dialog">`` for one slot: number of thread
colours (1-24), the parts, quick threads, "Find a thread …" (opens the thread
picker), own colour, and how the colour changes along the band (``dialog.*``).
Apply with ``Editor.set_colour_sequence``.
"""

from __future__ import annotations

from kvale_web.dom import Element, by_id
from kvale_web.state import AppState


class ColourDialog:
    def __init__(self, state: AppState) -> None:
        self.state = state
        self.dialog: Element = by_id("colour-dialog")

    def open(self, slot: int) -> None:
        """Show the dialog for colour slot ``slot`` (not built yet)."""
