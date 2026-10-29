"""Zoom: the zoom out / level / zoom in / fit buttons in ``#zoom-controls``.

Zoom is view-only state, kept here rather than in ``AppState``: 1 means "fit"
(the grid fills the space it has), the other levels scale that cell size
(``scene.ZOOM_LEVELS``). It applies to the drawing grid and the whole band.
Shortcuts: Ctrl + plus, Ctrl + minus and Ctrl + 0 (fit).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pyscript import document

from kvale_web.dom import Bindings, by_id
from kvale_web.grid.scene import ZOOM_LEVELS, zoom_step
from kvale_web.state import AppState

# Ctrl/Cmd + key: zoom in (1), out (-1) or fit (0); also the page zoom keys.
KEYS = {"+": 1, "=": 1, "-": -1, "_": -1, "0": 0}

_HTML = """
<button type="button" class="btn ghost icon-only" id="zoom-out" data-i18n-title="zoom.out" data-i18n-aria-label="zoom.out"><svg class="icon"><use href="#i-minus"/></svg></button>
<span class="zoom-label" id="zoom-label" aria-live="polite">100 %</span>
<button type="button" class="btn ghost icon-only" id="zoom-in" data-i18n-title="zoom.in" data-i18n-aria-label="zoom.in"><svg class="icon"><use href="#i-plus"/></svg></button>
<button type="button" class="btn ghost" id="zoom-fit" data-i18n-title="zoom.fit.hint"><svg class="icon"><use href="#i-fit"/></svg><span class="fit-label" data-i18n="zoom.fit">Tilpass</span></button>
"""


class ZoomControls:
    def __init__(self, state: AppState) -> None:
        self.state = state
        self.level = 1.0
        self.listeners: list[Callable[[], None]] = []
        self.container = by_id("zoom-controls")
        self.container.innerHTML = _HTML
        self.label = by_id("zoom-label")
        self.zoom_in = by_id("zoom-in")
        self.zoom_out = by_id("zoom-out")
        self.bindings = Bindings()
        self.bindings.on(self.zoom_in, "click", lambda _event: self.step(1))
        self.bindings.on(self.zoom_out, "click", lambda _event: self.step(-1))
        self.bindings.on(by_id("zoom-fit"), "click", lambda _event: self.set_level(1.0))
        # "+" cannot be named in a shortcuts.register combo, so listen here.
        self.bindings.on(document, "keydown", self.on_key)
        self.render()

    def on_key(self, event: Any) -> None:
        if not (event.ctrlKey or event.metaKey) or event.altKey:
            return
        action = KEYS.get(str(event.key))
        if action is None:
            return
        event.preventDefault()
        if action:
            self.step(action)
        else:
            self.set_level(1.0)

    def step(self, direction: int) -> None:
        self.set_level(zoom_step(self.level, direction))

    def set_level(self, level: float) -> None:
        if level == self.level:
            return
        self.level = level
        self.render()
        for listener in self.listeners:
            listener()

    def render(self, *_args: Any) -> None:
        self.label.textContent = f"{round(self.level * 100)} %"
        self.zoom_in.disabled = self.level >= ZOOM_LEVELS[-1]
        self.zoom_out.disabled = self.level <= ZOOM_LEVELS[0]
