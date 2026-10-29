"""Kvale in the browser: the PyScript user interface around ``kvale.core``.

Module map (see each module's docstring):

- ``app``: start-up and wiring of the views
- ``state``: ``AppState``, the single source of truth, with subscribe/notify
- ``i18n``: ``t(key, **values)`` and language switching
- ``dom``: element lookup and ``Bindings`` for event listeners
- ``shortcuts``: keyboard shortcut registry
- ``toolbar``: language menu, undo/redo, edit/preview switch, status line
- ``canvas``: the drawing grid and repeat preview
- ``panels``: side panels (colours, symmetry, grid settings, sequences)
- ``files``: open/save JSON, PNG export, autosave
"""
