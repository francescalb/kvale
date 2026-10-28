"""Top bar and status line: language menu, undo/redo, edit/preview switch.

``Toolbar`` binds to ``#lang``, ``#undo``, ``#redo``, ``#mode-edit``,
``#mode-preview`` and ``#status`` in ``index.html``, and registers the
Ctrl+Z / Ctrl+Y / Ctrl+Shift+Z and P shortcuts.
"""

from __future__ import annotations

import functools
from typing import Any

from kvale_web import i18n, shortcuts
from kvale_web.dom import Bindings, by_id
from kvale_web.i18n import t
from kvale_web.state import DOCUMENT, LANGUAGE, STATUS, VIEW, AppState


class Toolbar:
    def __init__(self, state: AppState) -> None:
        self.state = state
        self.language = by_id("lang")
        self.undo_button = by_id("undo")
        self.redo_button = by_id("redo")
        self.mode_edit = by_id("mode-edit")
        self.mode_preview = by_id("mode-preview")
        self.status = by_id("status")

        self.bindings = Bindings()
        self.bindings.on(self.language, "change", self.on_language)
        self.bindings.on(self.undo_button, "click", lambda _event: state.undo())
        self.bindings.on(self.redo_button, "click", lambda _event: state.redo())
        self.bindings.on(self.mode_edit, "click", lambda _event: state.set_mode("edit"))
        self.bindings.on(self.mode_preview, "click", lambda _event: state.set_mode("preview"))

        shortcuts.register("ctrl+z", lambda _event: state.undo())
        shortcuts.register("ctrl+y", lambda _event: state.redo())
        shortcuts.register("ctrl+shift+z", lambda _event: state.redo())
        shortcuts.register("p", lambda _event: self.toggle_mode())
        shortcuts.register("e", lambda _event: state.set_erase_tool(not state.erase_tool))
        for number in range(1, 10):
            shortcuts.register(str(number), functools.partial(self.select_slot, number - 1))

        state.subscribe(self.render, DOCUMENT, VIEW, STATUS, LANGUAGE)
        self.render()

    def select_slot(self, index: int, _event: Any) -> None:
        self.state.select_slot(index)

    def toggle_mode(self) -> None:
        self.state.set_mode("preview" if self.state.mode == "edit" else "edit")

    async def on_language(self, _event: Any) -> None:
        await i18n.set_language(str(self.language.value))
        self.state.notify(LANGUAGE)

    def render(self, _topic: str = "") -> None:
        editor = self.state.editor
        self.undo_button.disabled = not editor.can_undo
        self.redo_button.disabled = not editor.can_redo
        editing = self.state.mode == "edit"
        self.mode_edit.classList.toggle("active", editing)
        self.mode_preview.classList.toggle("active", not editing)
        self.mode_edit.setAttribute("aria-pressed", "true" if editing else "false")
        self.mode_preview.setAttribute("aria-pressed", "false" if editing else "true")
        self.language.value = i18n.current_language()
        self.status.textContent = status_text(self.state.status)


def status_text(status: tuple[str, dict[str, object]] | None) -> str:
    """Translate a status message; tuple/list values are lists of i18n keys."""
    if status is None:
        return ""
    key, values = status
    shown = {
        name: ", ".join(t(str(item)) for item in value)
        if isinstance(value, (tuple, list))
        else value
        for name, value in values.items()
    }
    return t(key, **shown)
