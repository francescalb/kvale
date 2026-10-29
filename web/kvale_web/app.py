"""Start-up: create the state and the views, then hide the loading screen.

``main.py`` (loaded by PyScript) only runs ``await start()``. To add a view,
construct it here after the state exists; views find their own elements and
subscribe to the state themselves.
"""

from __future__ import annotations

from pyscript import document, window

from kvale_web import i18n, shortcuts
from kvale_web.canvas import GridView
from kvale_web.dom import by_id
from kvale_web.panels import PalettePanel, SymmetryPanel
from kvale_web.state import AppState
from kvale_web.toolbar import Toolbar


class App:
    """Holds the state and the views so they live as long as the page."""

    def __init__(self, state: AppState) -> None:
        self.state = state
        self.toolbar = Toolbar(state)
        self.palette = PalettePanel(state)
        self.symmetry = SymmetryPanel(state)
        self.grid = GridView(state, by_id("grid"))


app: App | None = None


async def start() -> App:
    global app
    await i18n.set_language(i18n.initial_language())
    state = AppState()
    app = App(state)
    shortcuts.install()
    app.grid.render()
    document.body.classList.remove("booting")
    # Read by the browser tests to know the app is interactive.
    window.kvaleReady = True
    return app
