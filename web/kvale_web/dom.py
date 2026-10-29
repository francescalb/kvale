"""Small helpers around the browser DOM.

Every Python function handed to JavaScript must be wrapped in ``create_proxy``,
and that proxy lives until it is destroyed by hand. ``Bindings`` keeps the
proxies it creates so a view that rebuilds its elements (palette swatches,
sequence editor) can call ``destroy()`` first and leak nothing.

Usage::

    bindings = Bindings()
    bindings.on(by_id("undo"), "click", lambda event: state.undo())
    ...
    bindings.destroy()  # removes the listeners and frees the proxies

Async handlers (``async def``) work too; PyScript runs them as tasks.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from typing import Any

from pyodide.ffi import JsException
from pyscript import document, window
from pyscript.ffi import create_proxy

# JS objects have no type stubs; this alias marks where a DOM object is expected.
Element = Any
Handler = Callable[[Any], object]


def by_id(element_id: str) -> Element:
    """Return the element with this id, or raise if the page has none."""
    element = document.getElementById(element_id)
    if element is None:
        raise LookupError(f"No element with id {element_id!r}")
    return element


def query(selector: str, root: Element | None = None) -> Element | None:
    """First element matching a CSS selector, or None."""
    return (root or document).querySelector(selector)


def query_all(selector: str, root: Element | None = None) -> list[Element]:
    """All elements matching a CSS selector, as a Python list."""
    return list((root or document).querySelectorAll(selector))


def create(
    tag: str,
    *,
    class_name: str = "",
    text: str | None = None,
    attrs: dict[str, str] | None = None,
    parent: Element | None = None,
) -> Element:
    """Create an element, optionally with classes, text, attributes and a parent."""
    element = document.createElement(tag)
    if class_name:
        element.className = class_name
    if text is not None:
        element.textContent = text
    for name, value in (attrs or {}).items():
        element.setAttribute(name, value)
    if parent is not None:
        parent.appendChild(element)
    return element


def clear(element: Element) -> None:
    """Remove all children of an element."""
    element.replaceChildren()


def local_storage_get(key: str) -> str | None:
    """Read from localStorage; None if missing or storage is blocked."""
    try:
        value = window.localStorage.getItem(key)
    except JsException:  # storage can be blocked, e.g. in private mode
        return None
    return None if value is None else str(value)


def local_storage_set(key: str, value: str) -> None:
    """Write to localStorage; silently does nothing if storage is blocked."""
    with contextlib.suppress(JsException):  # storage can be blocked or full
        window.localStorage.setItem(key, value)


class Bindings:
    """Event listeners whose proxies can be released together."""

    def __init__(self) -> None:
        self._entries: list[tuple[Element, str, Any]] = []

    def on(self, target: Element, event_name: str, handler: Handler) -> None:
        """Call ``handler(event)`` when ``target`` fires ``event_name``."""
        proxy = create_proxy(handler)
        target.addEventListener(event_name, proxy)
        self._entries.append((target, event_name, proxy))

    def destroy(self) -> None:
        """Remove every listener added through this object and free its proxies."""
        for target, event_name, proxy in self._entries:
            target.removeEventListener(event_name, proxy)
            proxy.destroy()
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)
