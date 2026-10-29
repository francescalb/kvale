"""Files (chunk 6; a stub for now): new/open/save JSON, PNG export, autosave
and opening a pattern from the URL.

Belongs here (split into a ``files/`` package if it grows):

- ``#file-actions``: New / Open / Save / Save image buttons with icons
  (``#i-new``, ``#i-open``, ``#i-save``, ``#i-image``; strings ``file.*``),
  the hidden ``<input type="file">``, downloads (Blob + ``<a download>``),
  Ctrl+O / Ctrl+S via ``shortcuts.register``;
- ``#doc-info`` (hidden until filled): the file name and "Saved in this
  browser at {time}" (``autosave.*``);
- autosave to localStorage on ``DOCUMENT``, and restoring it at start (show
  ``#boot-restore`` on the loading screen while it opens);
- a pattern given in the URL (``?pattern=<url>``).

Load documents with ``state.load(document)`` so the history is reset and
every view re-renders. Report problems with ``state.set_status(key, ...)``.

Pillow is not loaded at start-up (it is about 1 MB and only needed for PNG
export). Call ``await ensure_pillow()`` before ``kvale.core.render_image``.
The thread list in the image should reuse chunk 5's list building in
``kvale_web.panels.thread_key``.
"""

from __future__ import annotations

from kvale_web.dom import Element, by_id
from kvale_web.state import AppState

_pillow_loaded = False


async def ensure_pillow() -> None:
    """Download and load Pillow into Pyodide on first use."""
    global _pillow_loaded
    if _pillow_loaded:
        return
    import pyodide_js

    await pyodide_js.loadPackage("pillow")
    _pillow_loaded = True


class FileViews:
    """Every chunk 6 view, kept alive as long as the page."""

    def __init__(self, state: AppState) -> None:
        self.state = state
        self.actions: Element = by_id("file-actions")
        self.doc_info: Element = by_id("doc-info")

    async def start(self) -> None:
        """Run once after every view exists: restore the autosave or the URL pattern."""


def mount(state: AppState) -> FileViews:
    return FileViews(state)
