"""Application state: the single source of truth for the browser UI.

``AppState`` wraps a core ``Editor`` (the document and its undo/redo history)
and adds the UI-only state (active colour slot, edit/preview mode, eraser,
status message). Views never change the document directly: they call
``state.edit(...)``, ``state.undo()`` and so on, and re-render when notified.

This module does not import ``js`` or ``pyscript``, so it runs and is tested in
normal CPython (see ``tests/test_web_state.py``).

Topics passed to listeners:

- ``DOCUMENT``: the pattern changed (edit, undo, redo, load, new). Undo/redo
  availability may also have changed.
- ``VIEW``: UI state changed (active slot, mode, eraser).
- ``STATUS``: the status message changed.
- ``LANGUAGE``: the interface language changed; re-render any text.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from kvale.core import Editor, EditResult, PatternDocument

DOCUMENT = "document"
VIEW = "view"
STATUS = "status"
LANGUAGE = "language"
TOPICS = (DOCUMENT, VIEW, STATUS, LANGUAGE)

Mode = Literal["edit", "preview"]
Listener = Callable[[str], None]

# Undo steps kept, the same as the Tkinter app.
HISTORY_LIMIT = 100


class AppState:
    def __init__(self, document: PatternDocument | None = None) -> None:
        self.editor = Editor(document, history_limit=HISTORY_LIMIT)
        self.active_slot = 0
        self.mode: Mode = "edit"
        self.erase_tool = False
        # Status message as an i18n key plus format values, so it can be
        # re-translated when the language changes. None means no message.
        self.status: tuple[str, dict[str, object]] | None = None
        self._listeners: list[tuple[Listener, frozenset[str]]] = []
        self._stroke_open = False

    @property
    def document(self) -> PatternDocument:
        """The current document. Read it fresh each render; undo replaces it."""
        return self.editor.document

    # Observers ---------------------------------------------------------

    def subscribe(self, listener: Listener, *topics: str) -> Callable[[], None]:
        """Call ``listener(topic)`` after changes to any of ``topics`` (all if none given).

        Returns a function that unsubscribes the listener.
        """
        unknown = set(topics) - set(TOPICS)
        if unknown:
            raise ValueError(f"Unknown topics: {sorted(unknown)}")
        entry = (listener, frozenset(topics or TOPICS))
        self._listeners.append(entry)

        def unsubscribe() -> None:
            if entry in self._listeners:
                self._listeners.remove(entry)

        return unsubscribe

    def notify(self, topic: str) -> None:
        """Tell the listeners for ``topic`` that it changed."""
        for listener, topics in list(self._listeners):
            if topic in topics:
                listener(topic)

    # Document edits ----------------------------------------------------

    def edit(self, action: Callable[[Editor], EditResult]) -> EditResult:
        """Run one ``Editor`` method and notify listeners if the document changed.

        Example: ``state.edit(lambda e: e.paint(x, y, state.active_slot))``.
        Square-only symmetry switched off by the edit is reported in the status.
        """
        result = action(self.editor)
        if result.removed_symmetry:
            self.set_status("symmetry_removed", operations=result.removed_symmetry)
        if result.changed:
            self._after_document_change()
        return result

    def begin_stroke(self) -> None:
        """Start a group of edits that undo as one step (e.g. a drag-paint stroke)."""
        if not self._stroke_open:
            self.editor.begin_batch()
            self._stroke_open = True

    def end_stroke(self) -> None:
        """Finish the group started by ``begin_stroke``. Safe to call when none is open."""
        if self._stroke_open:
            self._stroke_open = False
            self.editor.end_batch()
            # Undo availability only changes when the batch closes.
            self.notify(DOCUMENT)

    def undo(self) -> bool:
        self.end_stroke()
        if not self.editor.undo():
            return False
        self._after_document_change()
        return True

    def redo(self) -> bool:
        self.end_stroke()
        if not self.editor.redo():
            return False
        self._after_document_change()
        return True

    def load(self, document: PatternDocument) -> None:
        """Replace the document (open file, new pattern) and clear the history."""
        self.end_stroke()
        self.editor.load(document)
        self._after_document_change()

    def _after_document_change(self) -> None:
        # Undo of "add colour" can remove the active slot.
        slots = len(self.document.palette_sequences)
        if self.active_slot >= slots:
            self.active_slot = slots - 1
            self.notify(VIEW)
        self.notify(DOCUMENT)

    # UI state ----------------------------------------------------------

    def select_slot(self, index: int) -> None:
        """Make ``index`` the active colour slot and switch the eraser off."""
        if not 0 <= index < len(self.document.palette_sequences):
            return
        self.active_slot = index
        self.erase_tool = False
        self.notify(VIEW)

    def set_mode(self, mode: Mode) -> None:
        if mode != self.mode:
            self.end_stroke()
            self.mode = mode
            self.notify(VIEW)

    def set_erase_tool(self, enabled: bool) -> None:
        if enabled != self.erase_tool:
            self.erase_tool = enabled
            self.notify(VIEW)

    def set_status(self, key: str | None, **values: object) -> None:
        """Show an i18n message in the status line, or clear it with ``None``.

        Tuple or list values are taken as i18n keys: they are translated and
        joined with ", " when the message is shown.
        """
        self.status = None if key is None else (key, values)
        self.notify(STATUS)
