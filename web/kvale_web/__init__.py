"""Kvale in the browser: the PyScript user interface around ``kvale.core``.

Module map (see each module's docstring, and web/README.md for who owns what):

- ``app``: start-up; mounts the shell and each chunk's views
- ``state``: ``AppState``, the single source of truth, with subscribe/notify
- ``i18n``: ``t(key, **values)`` and language switching
- ``dom``: element lookup and ``Bindings`` for event listeners
- ``shortcuts``: keyboard shortcut registry
- ``shell``: language, theme, Draw / Whole band, undo/redo, toast (chunk 3)
- ``grid``: the drawing grid, tools, zoom, rulers, end pieces, corners (chunk 4)
- ``panels``: side panel cards and their dialogs (chunk 5)
- ``files``: new/open/save JSON, PNG export, autosave, URL parameter (chunk 6)
"""
