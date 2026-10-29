"""The "Repeat and size" card (chunk 5; a stub for now).

Belongs here, inside ``#grid-card`` (hidden until filled; remove ``hidden``):

- ``#grid-settings``: unit width/height and repeats across/down steppers
  (1-100, ``Editor.set_grid``), and "Add or remove a row/column …"
  (``grid.lines``) which calls ``lines.open_lines_dialog()``; strings ``grid.*``;
- ``#edge-toggles``: whether the outer left/right column and top/bottom row
  repeat, with the small diagram (``edges.*``).
"""

from __future__ import annotations

from kvale_web.dom import Element, by_id
from kvale_web.state import AppState


class GridSettingsPanel:
    def __init__(self, state: AppState) -> None:
        self.state = state
        self.card: Element = by_id("grid-card")
        self.settings: Element = by_id("grid-settings")
        self.edges: Element = by_id("edge-toggles")
