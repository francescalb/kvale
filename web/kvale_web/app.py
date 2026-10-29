"""Start-up: create the state and the views, then hide the loading screen.

``main.py`` (loaded by PyScript) only runs ``await start()``. Each chunk
mounts its own views through one ``mount(state)`` function, so chunks add
views in their own package and never need to edit this file:

- shell (chunk 3): ``kvale_web.shell.Shell``
- grid (chunk 4): ``kvale_web.grid.mount``
- panels (chunk 5): ``kvale_web.panels.mount``
- files (chunk 6): ``kvale_web.files.mount``
"""

from __future__ import annotations

from pyscript import document, window

from kvale_web import files, grid, i18n, panels, shortcuts
from kvale_web.shell import Shell
from kvale_web.state import AppState


class App:
    """Holds the state and the views so they live as long as the page."""

    def __init__(self, state: AppState) -> None:
        self.state = state
        self.shell = Shell(state)
        self.panels = panels.mount(state)
        self.files = files.mount(state)
        self.grid = grid.mount(state)


app: App | None = None


async def start() -> App:
    global app
    await i18n.set_language(i18n.initial_language())
    state = AppState()
    app = App(state)
    shortcuts.install()
    await app.files.start()
    app.grid.start()
    document.body.classList.remove("booting")
    # Read by the browser tests to know the app is interactive.
    window.kvaleReady = True
    return app
