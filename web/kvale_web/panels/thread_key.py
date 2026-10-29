"""The threads used in the pattern, under the whole band: ``#thread-key``.

Heading ``threads.title`` and one row per thread colour the stitches use, with
a chip and "DMC 321 Red" (``thread.code``), or "Own colour #123456". Hidden
while nothing is stitched.

The list itself is ``thread_rows(document)`` (in ``colour_model``, no DOM),
so the saved image (chunk 6) can list the same threads; ``row_text(info)``
gives the two texts of a row in the current language.
"""

from __future__ import annotations

from kvale_web.dom import by_id, clear, create
from kvale_web.panels.colour_model import ColourInfo, thread_rows
from kvale_web.panels.labels import code_text
from kvale_web.state import DOCUMENT, LANGUAGE, AppState

__all__ = ["ThreadKey", "row_text", "thread_rows"]


def row_text(info: ColourInfo) -> tuple[str, str]:
    """("DMC 321", "Red") or ("Own colour", "#123456")."""
    return code_text(info), info.name if info.is_thread else info.hex_colour


class ThreadKey:
    def __init__(self, state: AppState) -> None:
        self.state = state
        self.container = by_id("thread-key")
        self.list = by_id("thread-key-list")
        state.subscribe(lambda _topic: self.render(), DOCUMENT, LANGUAGE)
        self.render()

    def render(self) -> None:
        rows = thread_rows(self.state.document)
        clear(self.list)
        for info in rows:
            code, name = row_text(info)
            item = create("li", parent=self.list)
            create("i", class_name="chip", parent=item).style.background = info.hex_colour
            create("strong", text=code, parent=item)
            create("span", text=name, parent=item)
        self.container.hidden = not rows
