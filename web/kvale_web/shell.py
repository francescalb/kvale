"""The shared shell (chunk 3): language and theme, Draw / Whole band, undo/redo,
the toast, and the ``data-mode`` / ``data-target`` attributes on ``#stage``.

Binds to ``#lang-seg``, ``#theme-seg``, ``#mode-seg``, ``#undo``, ``#redo``,
``#stage`` and ``#toast`` in ``index.html``, and registers the
Ctrl+Z / Ctrl+Y / Ctrl+Shift+Z, P and 1-9 shortcuts.

Messages: any view calls ``state.set_status(key, **values)``; the shell shows
it in the toast (with Undo when there is something to undo) for a few seconds.
"""

from __future__ import annotations

import functools
from typing import Any

from pyscript import document, window
from pyscript.ffi import create_proxy

from kvale_web import i18n, shortcuts
from kvale_web.dom import Bindings, by_id, local_storage_get, local_storage_set, query_all
from kvale_web.i18n import t
from kvale_web.state import DOCUMENT, LANGUAGE, MODES, STATUS, VIEW, AppState

THEME_KEY = "kvale-theme"  # also read by the inline script in index.html
THEMES = ("light", "dark")
TOAST_MS = 6000


class Shell:
    def __init__(self, state: AppState) -> None:
        self.state = state
        self.stage = by_id("stage")
        self.undo_button = by_id("undo")
        self.redo_button = by_id("redo")
        self.lang_buttons = query_all("#lang-seg [data-lang]")
        self.theme_buttons = query_all("#theme-seg [data-theme-set]")
        self.mode_buttons = query_all("#mode-seg [data-mode]")
        self.toast = by_id("toast")
        self.toast_message = by_id("toast-message")
        self.toast_undo = by_id("toast-undo")
        self._toast_timer: int | None = None
        self._hide_toast_proxy = create_proxy(self._hide_toast)

        self.bindings = Bindings()
        for button in self.lang_buttons:
            self.bindings.on(button, "click", functools.partial(self.on_language, str(button.dataset.lang)))
        for button in self.theme_buttons:
            self.bindings.on(button, "click", functools.partial(self.on_theme, str(button.dataset.themeSet)))
        for button in self.mode_buttons:
            self.bindings.on(button, "click", functools.partial(self.on_mode, str(button.dataset.mode)))
        self.bindings.on(self.undo_button, "click", lambda _event: state.undo())
        self.bindings.on(self.redo_button, "click", lambda _event: state.redo())
        self.bindings.on(self.toast_undo, "click", self.on_toast_undo)
        # Follow the system theme while the user has not chosen one.
        self.dark_query = window.matchMedia("(prefers-color-scheme: dark)")
        self.bindings.on(self.dark_query, "change", lambda _event: self.render_theme())

        shortcuts.register("ctrl+z", lambda _event: state.undo())
        shortcuts.register("ctrl+y", lambda _event: state.redo())
        shortcuts.register("ctrl+shift+z", lambda _event: state.redo())
        shortcuts.register("p", lambda _event: self.toggle_mode())
        for number in range(1, 10):
            shortcuts.register(str(number), functools.partial(self.select_slot, number - 1))

        state.subscribe(self.render, DOCUMENT, VIEW, LANGUAGE)
        state.subscribe(self.show_status, STATUS, LANGUAGE)
        self.render()
        self.render_theme()

    # Actions -----------------------------------------------------------

    def select_slot(self, index: int, _event: Any) -> None:
        self.state.select_slot(index)

    def toggle_mode(self) -> None:
        self.state.set_mode("preview" if self.state.mode == "edit" else "edit")

    def on_mode(self, mode: str, _event: Any) -> None:
        # Matching against MODES gives a typed value (and ignores unknown ones).
        for known in MODES:
            if known == mode:
                self.state.set_mode(known)

    async def on_language(self, code: str, _event: Any) -> None:
        await i18n.set_language(code)
        self.state.notify(LANGUAGE)

    def on_theme(self, theme: str, _event: Any) -> None:
        if theme in THEMES:
            document.documentElement.dataset.theme = theme
            local_storage_set(THEME_KEY, theme)
            self.render_theme()
            # Canvases read colour tokens when they draw.
            self.state.notify(VIEW)

    def on_toast_undo(self, _event: Any) -> None:
        self.state.undo()
        self.state.set_status("history.undone")

    # Rendering ---------------------------------------------------------

    def current_theme(self) -> str:
        chosen = local_storage_get(THEME_KEY)
        if chosen in THEMES:
            return str(chosen)
        return "dark" if self.dark_query.matches else "light"

    def render_theme(self) -> None:
        theme = self.current_theme()
        for button in self.theme_buttons:
            pressed = str(button.dataset.themeSet) == theme
            button.setAttribute("aria-pressed", "true" if pressed else "false")

    def render(self, _topic: str = "") -> None:
        state = self.state
        self.undo_button.disabled = not state.editor.can_undo
        self.redo_button.disabled = not state.editor.can_redo
        self.stage.dataset.mode = state.mode
        self.stage.dataset.target = state.edit_target
        for button in self.mode_buttons:
            pressed = str(button.dataset.mode) == state.mode
            button.setAttribute("aria-pressed", "true" if pressed else "false")
        language = i18n.current_language()
        for button in self.lang_buttons:
            pressed = str(button.dataset.lang) == language
            button.setAttribute("aria-pressed", "true" if pressed else "false")

    def show_status(self, topic: str) -> None:
        if self.state.status is None:
            self._hide_toast()
            return
        self.toast_message.textContent = status_text(self.state.status)
        self.toast_undo.hidden = not self.state.editor.can_undo or self.state.status[0] == "history.undone"
        if topic == LANGUAGE:
            return  # re-translate only; do not show again or restart the timer
        self.toast.hidden = False
        if self._toast_timer is not None:
            window.clearTimeout(self._toast_timer)
        self._toast_timer = window.setTimeout(self._hide_toast_proxy, TOAST_MS)

    def _hide_toast(self) -> None:
        self._toast_timer = None
        self.toast.hidden = True


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
