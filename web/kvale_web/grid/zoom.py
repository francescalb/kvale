"""Zoom (chunk 4; a stub for now).

Belongs here: the zoom out / level / zoom in / fit buttons in
``#zoom-controls`` (``zoom.*``), and Ctrl+plus / Ctrl+minus through
``shortcuts.register``. Zoom is view-only state: keep it in this package
(e.g. on ``GridView``) rather than in ``AppState``, unless another chunk
needs it.
"""

from __future__ import annotations

from kvale_web.dom import Element, by_id
from kvale_web.state import AppState


class ZoomControls:
    def __init__(self, state: AppState) -> None:
        self.state = state
        self.container: Element = by_id("zoom-controls")
