"""Files (chunk 6 fills this in): open/save JSON, PNG export, autosave.

Belongs here: the Open/Save/Export/New buttons, the hidden
``<input type="file">``, downloads (Blob + ``<a download>``), Ctrl+O / Ctrl+S
via ``shortcuts.register``, and autosave to localStorage. Load documents with
``state.load(document)`` so the history is reset and every view re-renders.

Pillow is not loaded at start-up (it is about 1 MB and only needed for PNG
export). Call ``await ensure_pillow()`` before ``kvale.core.render_image``.
"""

from __future__ import annotations

_pillow_loaded = False


async def ensure_pillow() -> None:
    """Download and load Pillow into Pyodide on first use."""
    global _pillow_loaded
    if _pillow_loaded:
        return
    import pyodide_js

    await pyodide_js.loadPackage("pillow")
    _pillow_loaded = True
