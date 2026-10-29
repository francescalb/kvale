"""Stitch tools (chunk 4): the ``#tool-seg`` buttons and the ``#canvas-hint`` text.

Cross stitch and unpick work. The backstitch button (``#tool-back``) is
disabled in ``index.html`` until chunk 4 adds backstitch drawing; enabling it
is all this module needs. The colour chip on the cross-stitch button shows
the active colour slot. Shortcut E toggles unpick.
"""

from __future__ import annotations

import functools
from typing import Any

from kvale_web import shortcuts
from kvale_web.dom import Bindings, by_id, query_all
from kvale_web.i18n import t
from kvale_web.state import DOCUMENT, LANGUAGE, TOOLS, VIEW, AppState, Tool

# i18n key of the hint under the grid for each tool.
HINT_KEYS: dict[Tool, str] = {
    "cross": "canvas.hint.cross",
    "back": "canvas.hint.back",
    "unpick": "canvas.hint.unpick",
}


class ToolPicker:
    def __init__(self, state: AppState) -> None:
        self.state = state
        self.buttons = query_all("#tool-seg [data-tool]")
        self.chip = by_id("tool-chip")
        self.hint = by_id("canvas-hint")
        self.bindings = Bindings()
        for button in self.buttons:
            self.bindings.on(button, "click", functools.partial(self.on_tool, str(button.dataset.tool)))
        shortcuts.register("e", lambda _event: self.toggle_unpick())
        state.subscribe(lambda _topic: self.render(), DOCUMENT, VIEW, LANGUAGE)
        self.render()

    def on_tool(self, tool: str, _event: Any) -> None:
        # Matching against TOOLS gives a typed value (and ignores unknown ones).
        for known in TOOLS:
            if known == tool:
                self.state.set_tool(known)

    def toggle_unpick(self) -> None:
        self.state.set_tool("cross" if self.state.tool == "unpick" else "unpick")

    def render(self) -> None:
        tool = self.state.tool
        for button in self.buttons:
            pressed = str(button.dataset.tool) == tool
            button.setAttribute("aria-pressed", "true" if pressed else "false")
        palette = self.state.document.palette
        self.chip.style.background = palette[self.state.active_slot % len(palette)]
        # Keep data-i18n in step so apply_translations() keeps the right text.
        self.hint.dataset.i18n = HINT_KEYS[tool]
        self.hint.textContent = t(HINT_KEYS[tool])
