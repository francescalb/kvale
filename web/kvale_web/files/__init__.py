"""Files (chunk 6): new/open/save JSON, PNG export, autosave and a pattern
given in the page URL.

- ``logic``: everything that needs no browser (reading and writing pattern
  files, file names, unsaved changes, the autosave record, URL parsing, the
  PNG). Tested in CPython.
- ``browser``: small wrappers around browser APIs (downloads, the file
  pickers, localStorage, fetch).
- ``views``: ``FileViews``, which fills ``#file-actions``, ``#doc-info`` and
  ``#boot-restore``.

This module imports the browser parts only when called, so ``logic`` can be
imported in plain CPython.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kvale_web.files.views import FileViews
    from kvale_web.state import AppState


async def ensure_pillow() -> None:
    """Download and load Pillow into Pyodide on first use (it is not loaded at start)."""
    from kvale_web.files import browser

    await browser.ensure_pillow()


def mount(state: AppState) -> FileViews:
    from kvale_web.files.views import FileViews

    return FileViews(state)
