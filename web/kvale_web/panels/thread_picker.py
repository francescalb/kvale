"""The thread picker (chunk 5; a stub for now).

Belongs here: ``<dialog id="thread-dialog">`` with the thread brand selector
(DMC; Anchor and Madeira listed but disabled as "coming later"), search
("DMC 321" finds the same as "321"), colour families, the list, and own
colour (``thread.*``). Colours come from ``kvale.core.dmc``. A code is always
shown with its brand: ``t("thread.code", system="DMC", code="321")``.
"""

from __future__ import annotations

from kvale_web.dom import Element, by_id
from kvale_web.state import AppState


class ThreadPicker:
    def __init__(self, state: AppState) -> None:
        self.state = state
        self.dialog: Element = by_id("thread-dialog")
