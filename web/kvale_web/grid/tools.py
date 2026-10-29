"""Stitch tools: the ``#tool-seg`` buttons and the ``#canvas-hint`` text.

Cross stitch, backstitch and unpick. The colour chip on the cross-stitch
button shows the active colour slot. The hint under the grid explains the
chosen tool and what the current target offers (rulers in the unit, the
faded neighbours of an end or a corner).

Shortcuts: X cross stitch, B backstitch, E toggles unpick.
"""

from __future__ import annotations

import functools
from typing import Any

from kvale_web import shortcuts
from kvale_web.dom import Bindings, by_id, query_all
from kvale_web.grid.scene import is_corner
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
        # The hint is built here from two strings; keep apply_translations() off it.
        self.hint.removeAttribute("data-i18n")
        by_id("tool-back").disabled = False
        self.bindings = Bindings()
        for button in self.buttons:
            self.bindings.on(button, "click", functools.partial(self.on_tool, str(button.dataset.tool)))
        shortcuts.register("e", lambda _event: self.toggle_unpick())
        shortcuts.register("b", lambda _event: state.set_tool("back"))
        shortcuts.register("x", lambda _event: state.set_tool("cross"))
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
        state = self.state
        tool = state.tool
        for button in self.buttons:
            pressed = str(button.dataset.tool) == tool
            button.setAttribute("aria-pressed", "true" if pressed else "false")
        palette = state.document.palette
        self.chip.style.background = palette[state.active_slot % len(palette)]
        target = state.edit_target
        place = "canvas.hint.edges" if target == "unit" else "canvas.hint.corner" if is_corner(target) else "canvas.hint.end"
        self.hint.textContent = f"{t(HINT_KEYS[tool])} {t(place)}"
