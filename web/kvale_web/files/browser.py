"""Browser APIs used by the file views: downloads, the file pickers, storage,
fetch and Pillow loading. Kept apart from ``views`` so the views read as UI.
"""

from __future__ import annotations

import contextlib
from typing import Any

from pyodide.ffi import JsException, to_js
from pyscript import document, fetch, window

_pillow_loaded = False


async def ensure_pillow() -> None:
    """Download and load Pillow into Pyodide on first use."""
    global _pillow_loaded
    if _pillow_loaded:
        return
    import pyodide_js

    await pyodide_js.loadPackage("pillow")
    _pillow_loaded = True


def js_object(value: dict[str, Any]) -> Any:
    """A plain JavaScript object (not a Map) from a Python dict."""
    return to_js(value, dict_converter=window.Object.fromEntries)


def make_blob(data: str | bytes, mime: str) -> Any:
    part = to_js(data) if isinstance(data, bytes) else data
    return window.Blob.new(to_js([part]), js_object({"type": mime}))


def download(data: str | bytes, file_name: str, mime: str) -> None:
    """Hand the browser a file to save under ``file_name``."""
    url = window.URL.createObjectURL(make_blob(data, mime))
    link = document.createElement("a")
    link.href = url
    link.download = file_name
    link.hidden = True
    document.body.appendChild(link)
    link.click()
    link.remove()
    # Revoke later: some browsers read the blob after click() returns.
    window.setTimeout(window.URL.revokeObjectURL.bind(window.URL, url), 60_000)


# File System Access API (Chrome, Edge) --------------------------------

_PICKER_TYPES = [{"description": "Kvale", "accept": {"application/json": [".json"]}}]


def has_open_picker() -> bool:
    return bool(getattr(window, "showOpenFilePicker", None))


def is_abort(error: JsException) -> bool:
    """True when the user closed a picker without choosing."""
    return str(getattr(error, "name", "")) == "AbortError" or "AbortError" in str(error)


async def pick_file() -> tuple[str, str, Any] | None:
    """Ask for a pattern file; return (file name, text, handle) or None if cancelled."""
    try:
        handles = await window.showOpenFilePicker(
            js_object({"types": _PICKER_TYPES, "multiple": False})
        )
    except JsException as error:
        if is_abort(error):
            return None
        raise
    handle = handles[0]
    file = await handle.getFile()
    return str(file.name), str(await file.text()), handle


async def write_handle(handle: Any, text: str) -> bool:
    """Write ``text`` to a file chosen in the picker; False if that is not allowed."""
    if not getattr(handle, "createWritable", None):
        return False
    try:
        options = js_object({"mode": "readwrite"})
        granted = str(await handle.queryPermission(options)) == "granted"
        if not granted and str(await handle.requestPermission(options)) != "granted":
            return False
        writable = await handle.createWritable()
        await writable.write(text)
        await writable.close()
    except JsException:
        return False
    return True


# Storage, time, fetch -------------------------------------------------


def storage_get(key: str) -> str | None:
    try:
        value = window.localStorage.getItem(key)
    except JsException:  # blocked, e.g. in private mode
        return None
    return None if value is None else str(value)


def storage_set(key: str, value: str) -> bool:
    try:
        window.localStorage.setItem(key, value)
    except JsException:  # blocked or full
        return False
    return True


def storage_remove(key: str) -> None:
    with contextlib.suppress(JsException):
        window.localStorage.removeItem(key)


def now_ms() -> float:
    return float(window.Date.now())


def clock_time(time_ms: float, language: str) -> str:
    """Hours and minutes of a JavaScript time, as the language writes them."""
    date = window.Date.new(time_ms)
    try:
        return str(date.toLocaleTimeString(language, js_object({"hour": "2-digit", "minute": "2-digit"})))
    except JsException:
        return f"{int(date.getHours()):02d}:{int(date.getMinutes()):02d}"


async def fetch_text(url: str) -> str | None:
    """The text at ``url``, or None if it cannot be fetched."""
    try:
        response = await fetch(url)
        if not response.ok:
            return None
        return str(await response.text())
    except (JsException, OSError):
        return None


def forget_url_pattern() -> None:
    """Drop ``?example=`` / ``?file=`` / ``#data=`` from the address bar, so a
    reload restores the autosave (with the user's edits) instead."""
    with contextlib.suppress(JsException):
        window.history.replaceState(None, "", str(window.location.pathname))
