"""``FileViews``: the New / Open / Save / Save as / Save image buttons (``#file-actions``),
the pattern name with its unsaved marker and the autosave note (``#doc-info``),
autosave to localStorage, and opening a pattern at start (from the URL, or
the autosave while ``#boot-restore`` shows on the loading screen).
"""

from __future__ import annotations

import asyncio
from typing import Any

from pyodide.ffi import JsException
from pyscript import window
from pyscript.ffi import create_proxy

from kvale.core import PatternDocument
from kvale_web import i18n, shortcuts
from kvale_web.dom import Bindings, Element, by_id, create
from kvale_web.files import browser
from kvale_web.files.logic import (
    AUTOSAVE_KEY,
    JSON_EXTENSION,
    PNG_EXTENSION,
    DocSession,
    OpenError,
    UrlSource,
    autosave_payload,
    decode_data_hash,
    file_name,
    parse_document,
    read_autosave,
    render_png,
    serialize,
    stem_of,
    url_source,
)
from kvale_web.i18n import t
from kvale_web.panels.colour_model import thread_rows
from kvale_web.panels.labels import full_text
from kvale_web.state import DOCUMENT, LANGUAGE, AppState

# Wait this long after the last change before writing the autosave, so a
# drag stroke writes once rather than once per square.
AUTOSAVE_DELAY_MS = 400

_BUTTONS = (
    # id, icon, label key, tooltip key
    ("file-new", "i-new", "file.new", "file.new.hint"),
    ("file-open", "i-open", "file.open", "file.open.hint"),
    ("file-save", "i-save", "file.save", "file.save.hint"),
    ("file-save-as", "i-save-as", "file.saveAs", "file.saveAs.hint"),
    ("file-export", "i-image", "file.export", "file.export.hint"),
)


class FileViews:
    """Every chunk 6 view, kept alive as long as the page."""

    def __init__(self, state: AppState) -> None:
        self.state = state
        self.session = DocSession(state.document)
        self.handle: Any = None  # File System Access handle of the open file, if any
        self.saved_at: float | None = None  # time of the last autosave
        self.exporting = False
        self._timer: int | None = None
        self._flush_proxy = create_proxy(self._on_timer)
        self.bindings = Bindings()

        self.actions: Element = by_id("file-actions")
        self.doc_info: Element = by_id("doc-info")
        self._build_actions()
        self._build_doc_info()

        shortcuts.register("ctrl+o", lambda _event: self.open())
        # Async handlers are passed as they are (not wrapped in a lambda), so
        # the browser glue sees the coroutine function and runs it.
        shortcuts.register("ctrl+s", self.save)
        shortcuts.register("ctrl+shift+s", self.save_as)
        self.bindings.on(window, "beforeunload", self._on_before_unload)
        self.bindings.on(window, "pagehide", lambda _event: self.flush())
        state.subscribe(self._on_document, DOCUMENT)
        state.subscribe(lambda _topic: self.render(), LANGUAGE)
        self.render()

    # Building ----------------------------------------------------------

    def _build_actions(self) -> None:
        self.buttons: dict[str, Element] = {}
        for element_id, icon, label, hint in _BUTTONS:
            button = create(
                "button",
                class_name="btn",
                attrs={"type": "button", "id": element_id, "data-i18n-title": hint, "title": t(hint)},
                parent=self.actions,
            )
            button.innerHTML = f'<svg class="icon" aria-hidden="true"><use href="#{icon}"/></svg>'
            create("span", text=t(label), attrs={"data-i18n": label}, parent=button)
            self.buttons[element_id] = button
        self.input = create(
            "input",
            attrs={"type": "file", "id": "file-input", "accept": ".json,application/json", "hidden": ""},
            parent=self.actions,
        )
        self.bindings.on(self.buttons["file-new"], "click", lambda _event: self.new())
        self.bindings.on(self.buttons["file-open"], "click", lambda _event: self.open())
        self.bindings.on(self.buttons["file-save"], "click", self.save)
        self.bindings.on(self.buttons["file-save-as"], "click", self.save_as)
        self.bindings.on(self.buttons["file-export"], "click", self.export_png)
        self.bindings.on(self.input, "change", self._on_input_change)

    def _build_doc_info(self) -> None:
        info = self.doc_info
        name_row = create("span", class_name="docname", parent=info)
        self.name_text = create("span", attrs={"id": "doc-name"}, parent=name_row)
        self.unsaved_mark = create(
            "span",
            class_name="unsaved",
            text="●",
            attrs={"id": "doc-unsaved", "role": "img", "data-i18n-title": "file.unsaved",
                   "data-i18n-aria-label": "file.unsaved"},
            parent=name_row,
        )
        self.autosave_note = create(
            "span",
            class_name="autosave",
            attrs={"id": "autosave-note", "data-i18n-title": "autosave.hint", "hidden": ""},
            parent=info,
        )
        create("span", class_name="dot", attrs={"aria-hidden": "true"}, parent=self.autosave_note)
        self.autosave_text = create("span", parent=self.autosave_note)
        info.hidden = False

    # Rendering ---------------------------------------------------------

    def render(self) -> None:
        dirty = self.session.is_dirty(self.state.document)
        self.name_text.textContent = self.session.display_name(t("file.untitled"))
        self.unsaved_mark.hidden = not dirty
        self.unsaved_mark.title = t("file.unsaved")
        self.unsaved_mark.setAttribute("aria-label", t("file.unsaved"))
        self.doc_info.dataset.dirty = "true" if dirty else "false"
        self.autosave_note.title = t("autosave.hint")
        if self.saved_at is not None:
            time = browser.clock_time(self.saved_at, i18n.current_language())
            self.autosave_text.textContent = t("autosave.saved", time=time)
            self.autosave_note.hidden = False
        if self.exporting:
            self._set_export_label("file.export.preparing")

    def _set_export_label(self, key: str) -> None:
        label = self.buttons["file-export"].querySelector("span")
        label.dataset.i18n = key
        label.textContent = t(key)

    # Autosave ----------------------------------------------------------

    def _on_document(self, _topic: str) -> None:
        if self._timer is not None:
            window.clearTimeout(self._timer)
        self._timer = window.setTimeout(self._flush_proxy, AUTOSAVE_DELAY_MS)

    def _on_timer(self) -> None:
        self._timer = None
        self.flush()

    def flush(self) -> None:
        """Write the autosave now and update the name and unsaved marker."""
        if self._timer is not None:
            window.clearTimeout(self._timer)
            self._timer = None
        time_ms = browser.now_ms()
        payload = autosave_payload(
            serialize(self.state.document), self.session.name, self.session.saved_fingerprint, time_ms
        )
        if browser.storage_set(AUTOSAVE_KEY, payload):
            self.saved_at = time_ms
        self.render()

    def _on_before_unload(self, event: Any) -> None:
        self.flush()
        if self.session.is_dirty(self.state.document):
            event.preventDefault()
            event.returnValue = ""  # older browsers need this to ask

    # Start-up ----------------------------------------------------------

    async def start(self) -> None:
        """Open the pattern named in the URL, or else restore the autosave."""
        location = window.location
        source = url_source(str(location.search), str(location.hash))
        if source is not None:
            opened = await self._open_url(source)
            browser.forget_url_pattern()
            if opened:
                return
        saved = read_autosave(browser.storage_get(AUTOSAVE_KEY))
        if saved is None:
            return
        restore_note = by_id("boot-restore")
        restore_note.hidden = False
        await asyncio.sleep(0)  # let the note show
        self.state.load(saved.document)
        self.session.reset(saved.document, saved.name)
        self.session.saved_fingerprint = saved.saved_fingerprint
        self.saved_at = saved.time_ms
        self.render()

    async def _open_url(self, source: UrlSource) -> bool:
        if source.kind == "data":
            try:
                text = decode_data_hash(source.value)
            except OpenError as error:
                self.state.set_status(error.key)
                return False
            return self._open_text(text, source.name, handle=None)
        fetched = await browser.fetch_text(source.fetch_url())
        if fetched is None:
            self.state.set_status("file.error.fetch")
            return False
        return self._open_text(fetched, source.name, handle=None)

    # Actions -----------------------------------------------------------

    def _may_discard(self) -> bool:
        """True if there are no unsaved changes, or the user agrees to lose them."""
        self.flush()
        if not self.session.is_dirty(self.state.document):
            return True
        return bool(window.confirm(t("file.confirmDiscard")))

    def new(self) -> None:
        if not self._may_discard():
            return
        document = PatternDocument()
        self.handle = None
        self.session.reset(document, None)
        self.state.load(document)
        self.render()

    def open(self) -> None:
        """Ask for a pattern file. Runs inside the click/keydown, which the pickers need."""
        if not self._may_discard():
            return
        if browser.has_open_picker():
            asyncio.ensure_future(self._open_with_picker())
        else:
            self.input.value = ""
            self.input.click()

    async def _open_with_picker(self) -> None:
        try:
            picked = await browser.pick_file()
        except JsException:
            # The picker failed (blocked, not allowed here): use the plain input.
            self.input.value = ""
            self.input.click()
            return
        if picked is not None:
            name, text, handle = picked
            self._open_text(text, stem_of(name), handle)

    async def _on_input_change(self, _event: Any) -> None:
        files = self.input.files
        if not files or not files.length:
            return
        file = files.item(0)
        try:
            text = str(await file.text())
        except JsException:
            self.state.set_status("file.error.notPattern")
            return
        finally:
            self.input.value = ""
        self._open_text(text, stem_of(str(file.name)), handle=None)

    def _open_text(self, text: str, name: str | None, handle: Any) -> bool:
        try:
            document = parse_document(text)
        except OpenError as error:
            self.state.set_status(error.key)
            return False
        self.handle = handle
        self.session.reset(document, name or None)
        self.state.load(document)
        self.flush()
        return True

    async def save(self, _event: Any = None) -> None:
        document = self.state.document
        text = serialize(document)
        if self.handle is None or not await browser.write_handle(self.handle, text):
            name = file_name(self.session.name, JSON_EXTENSION, t("file.untitled"))
            browser.download(text, name, "application/json")
            self.session.mark_saved(document, stem_of(name))
        else:
            self.session.mark_saved(document)
        self.flush()

    async def save_as(self, _event: Any = None) -> None:
        """Save under a new name (Ctrl+Shift+S); later saves go to that file.

        Where the browser can ask for a place (Chrome, Edge), it does; elsewhere
        the file is downloaded, which most browsers let you name.
        """
        document = self.state.document
        text = serialize(document)
        name = file_name(self.session.name, JSON_EXTENSION, t("file.untitled"))
        if browser.has_save_picker():
            try:
                handle = await browser.pick_save_file(name)
            except JsException:
                handle = False  # the picker failed: download instead
            if handle is None:
                return  # cancelled
            if handle and await browser.write_handle(handle, text):
                self.handle = handle
                self.session.mark_saved(document, stem_of(str(handle.name)))
                self.flush()
                return
        browser.download(text, name, "application/json")
        self.handle = None
        self.session.mark_saved(document, stem_of(name))
        self.flush()

    async def export_png(self, _event: Any = None) -> None:
        if self.exporting:
            return
        button = self.buttons["file-export"]
        self.exporting = True
        button.disabled = True
        button.setAttribute("aria-busy", "true")
        self._set_export_label("file.export.preparing")
        try:
            await asyncio.sleep(0.05)  # let "Preparing the image …" show first
            await browser.ensure_pillow()
            document = self.state.document
            # The thread list under the whole band, also in the image.
            key = [(info.hex_colour, full_text(info)) for info in thread_rows(document)]
            data = render_png(document, key, t("threads.title"))
            name = file_name(self.session.name, PNG_EXTENSION, t("file.untitled"))
            browser.download(data, name, "image/png")
        except Exception:  # noqa: BLE001 - any failure becomes a message, not a crash
            self.state.set_status("file.error.export")
        finally:
            self.exporting = False
            button.disabled = False
            button.removeAttribute("aria-busy")
            self._set_export_label("file.export")
