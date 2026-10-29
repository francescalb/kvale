"""The threads used in the pattern, under the whole band (chunk 5; a stub for now).

Belongs here: ``#thread-key`` in the whole-band view (hidden until filled):
heading ``threads.title`` and one row per thread colour used, with a chip and
"DMC 321 Christmas Red Bright" (``thread.code``), or the own colour's hex.
Chunk 6 draws the same list into the PNG export; put the list building in a
function without DOM access (e.g. ``thread_rows(document)``) so it can reuse
it.
"""

from __future__ import annotations

from kvale_web.dom import Element, by_id
from kvale_web.state import AppState


class ThreadKey:
    def __init__(self, state: AppState) -> None:
        self.state = state
        self.container: Element = by_id("thread-key")
