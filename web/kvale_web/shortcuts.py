"""Keyboard shortcuts: one ``keydown`` listener on the document and a registry.

Any module registers its own shortcuts, so chunks do not edit a shared function::

    shortcuts.register("ctrl+s", save_json)        # Ctrl+S, or Cmd+S on macOS
    shortcuts.register("ctrl+shift+z", redo)
    shortcuts.register("e", toggle_eraser)

Key names are ``KeyboardEvent.key`` in lower case, with ``ctrl+``, ``shift+``
and ``alt+`` modifiers in that order. ``ctrl`` also matches the Cmd key. The
handler gets the event; the default browser action is prevented. Plain keys
(without ``ctrl``/``alt``) are ignored while the user types in a text field.
No shortcut runs while a modal dialog is open: they act on the pattern behind
it, and the dialog's own fields keep their keys (Ctrl+Z undoes typing there).
Handlers may be ``async def``.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from typing import Any

from pyscript import document

from kvale_web.dom import Bindings

Handler = Callable[[Any], object]

_handlers: dict[str, Handler] = {}
_bindings = Bindings()
_TEXT_INPUTS = ("text", "number", "search", "email", "url", "password", "")


def register(combo: str, handler: Handler) -> None:
    """Call ``handler(event)`` for ``combo``; replaces an earlier handler for it."""
    _handlers[normalise(combo)] = handler


def normalise(combo: str) -> str:
    parts = [part.strip().lower() for part in combo.split("+")]
    key = parts[-1]
    modifiers = set(parts[:-1])
    unknown = modifiers - {"ctrl", "shift", "alt"}
    if unknown:
        raise ValueError(f"Unknown modifier in {combo!r}: {sorted(unknown)}")
    return "+".join([m for m in ("ctrl", "shift", "alt") if m in modifiers] + [key])


def combo_of(event: Any) -> str:
    parts = []
    if event.ctrlKey or event.metaKey:
        parts.append("ctrl")
    if event.shiftKey:
        parts.append("shift")
    if event.altKey:
        parts.append("alt")
    parts.append(str(event.key).lower())
    return "+".join(parts)


def _is_typing(event: Any) -> bool:
    target = event.target
    tag = str(getattr(target, "tagName", "") or "")
    if tag in ("TEXTAREA", "SELECT") or getattr(target, "isContentEditable", False):
        return True
    return tag == "INPUT" and str(target.type) in _TEXT_INPUTS


def dialog_open() -> bool:
    """True while a modal dialog (a ``<dialog>`` opened with ``showModal``) is open."""
    return any(bool(dialog.matches(":modal")) for dialog in document.querySelectorAll("dialog[open]"))


def _on_keydown(event: Any) -> None:
    handler = _handlers.get(combo_of(event))
    if handler is None or dialog_open():
        return
    if not (event.ctrlKey or event.metaKey or event.altKey) and _is_typing(event):
        return
    event.preventDefault()
    result = handler(event)
    if inspect.isawaitable(result):
        asyncio.ensure_future(result)


def install() -> None:
    """Start listening for shortcuts (called once by ``app.start``)."""
    if not len(_bindings):
        _bindings.on(document, "keydown", _on_keydown)
