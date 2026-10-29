"""The side panel and its dialogs (chunk 5).

``app.py`` calls ``mount(state)`` once. Add new views to ``PanelViews`` here,
so ``app.py`` and the other chunks never need to change.

Modules: ``colours`` (Colours card), ``symmetry`` (Symmetry card),
``grid_settings`` (Repeat and size card, edge toggles), ``colour_dialog``,
``thread_picker``, ``lines`` (rows and columns dialog) and ``thread_key``
(threads under the whole band).
"""

from __future__ import annotations

from kvale_web.panels.colour_dialog import ColourDialog
from kvale_web.panels.colours import ColoursPanel
from kvale_web.panels.grid_settings import GridSettingsPanel
from kvale_web.panels.lines import LinesDialog
from kvale_web.panels.symmetry import SymmetryPanel
from kvale_web.panels.thread_key import ThreadKey
from kvale_web.panels.thread_picker import ThreadPicker
from kvale_web.state import AppState


class PanelViews:
    """Every chunk 5 view, kept alive as long as the page."""

    def __init__(self, state: AppState) -> None:
        self.colours = ColoursPanel(state)
        self.symmetry = SymmetryPanel(state)
        self.grid_settings = GridSettingsPanel(state)
        self.colour_dialog = ColourDialog(state)
        self.thread_picker = ThreadPicker(state)
        self.lines = LinesDialog(state)
        self.thread_key = ThreadKey(state)


def mount(state: AppState) -> PanelViews:
    return PanelViews(state)
