"""Rulers and the row/column popover (chunk 4; a stub for now).

Belongs here: the numbered buttons in ``#ruler-top`` and ``#ruler-left``
(set ``--ruler`` on ``.editor`` in grid.css when they are shown), and the
``#edge-popover`` menu that inserts or removes a row or column
(``Editor.insert_row`` and friends; ``edge.*``, ``grid.colN`` ...).
"More options …" (``edge.more``) opens chunk 5's rows and columns dialog
with ``kvale_web.panels.lines.open_lines_dialog()``.
"""

from __future__ import annotations

from kvale_web.dom import Element, by_id
from kvale_web.state import AppState


class Rulers:
    def __init__(self, state: AppState) -> None:
        self.state = state
        self.top: Element = by_id("ruler-top")
        self.left: Element = by_id("ruler-left")
        self.popover: Element = by_id("edge-popover")
