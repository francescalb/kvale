"""Application state: the single source of truth for the browser UI.

``AppState`` wraps a core ``Editor`` (the document and its undo/redo history)
and adds the UI-only state shared by every view:

- ``active_slot``: the colour slot new cross stitches and backstitches use;
- ``tool``: the stitch tool, ``"cross"``, ``"back"`` (backstitch) or ``"unpick"``;
- ``edit_target``: what the grid edits, ``"unit"`` (the repeat), an end piece
  (``"top"``, ``"bottom"``, ``"left"``, ``"right"``) or a corner
  (``"top_left"``, ``"top_right"``, ``"bottom_left"``, ``"bottom_right"``);
- ``mode``: ``"edit"`` (draw) or ``"preview"`` (the whole band);
- ``status``: the latest message for the user.

Views never change the document directly: they call ``state.edit(...)``,
``state.undo()`` and so on, and re-render when notified. Pointer input goes
through ``paint_cell``/``erase_cell``, which edit the current ``edit_target``;
on the unit they only accept cells in the minimal cell (``editable_cells``).

This module does not import ``js`` or ``pyscript``, so it runs and is tested in
normal CPython (see ``tests/test_web_state.py``).

Topics passed to listeners:

- ``DOCUMENT``: the pattern changed (edit, undo, redo, load, new). Undo/redo
  availability may also have changed.
- ``VIEW``: UI state changed (``active_slot``, ``tool``, ``edit_target``, ``mode``).
- ``STATUS``: the status message changed.
- ``LANGUAGE``: the interface language changed; re-render any text.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from kvale.core import Editor, EditResult, PatternDocument
from kvale.core.editing import CORNERS, EDGES, EditTarget
from kvale.core.symmetry import minimal_cell

DOCUMENT = "document"
VIEW = "view"
STATUS = "status"
LANGUAGE = "language"
TOPICS = (DOCUMENT, VIEW, STATUS, LANGUAGE)

Mode = Literal["edit", "preview"]
MODES: tuple[Mode, ...] = ("edit", "preview")
Tool = Literal["cross", "back", "unpick"]
TOOLS: tuple[Tool, ...] = ("cross", "back", "unpick")
# Everything the grid can edit, in the order of the "Drawing in" bar.
EDIT_TARGETS: tuple[EditTarget, ...] = ("unit", *EDGES, *CORNERS)
# i18n key naming each edit target (the bar's buttons).
TARGET_LABEL_KEYS: dict[EditTarget, str] = {
    "unit": "target.unit",
    "top": "target.top",
    "bottom": "target.bottom",
    "left": "target.left",
    "right": "target.right",
    "top_left": "target.tl",
    "top_right": "target.tr",
    "bottom_left": "target.bl",
    "bottom_right": "target.br",
}
Listener = Callable[[str], None]

# Undo steps kept, the same as the old Tkinter app had.
HISTORY_LIMIT = 100


class AppState:
    def __init__(self, document: PatternDocument | None = None) -> None:
        self.editor = Editor(document, history_limit=HISTORY_LIMIT)
        self.active_slot = 0
        self.mode: Mode = "edit"
        self.tool: Tool = "cross"
        self.edit_target: EditTarget = "unit"
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
            self.set_status("symmetry.switchedOff")
        if result.changed:
            self._after_document_change()
        return result

    @property
    def editable_cells(self) -> frozenset[tuple[int, int]]:
        """The minimal cell: the unit cells the user may paint (see ``minimal_cell``).

        The symmetry copies these cells onto the rest of the unit. It is cached
        in core, so reading it on every render and pointer event is cheap.
        """
        doc = self.document
        return minimal_cell(doc.unit_width, doc.unit_height, doc.symmetry)

    def paint_cell(self, x: int, y: int) -> EditResult:
        """Cross-stitch cell (x, y) of ``edit_target`` in the active slot.

        On the unit, cells outside the minimal cell do nothing. On an end piece
        or a corner, core ignores cells outside it (see ``editing.editor_bounds``).
        """
        target = self.edit_target
        if target == "unit" and (x, y) not in self.editable_cells:
            return EditResult(False)
        slot = self.active_slot
        return self.edit(lambda editor: editor.paint(x, y, slot, target))

    def erase_cell(self, x: int, y: int) -> EditResult:
        """Unpick cell (x, y) of ``edit_target``; on the unit only inside the minimal cell."""
        target = self.edit_target
        if target == "unit" and (x, y) not in self.editable_cells:
            return EditResult(False)
        return self.edit(lambda editor: editor.erase(x, y, target))

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
        """Replace the document (open file, new pattern) and clear the history.

        The grid goes back to drawing in the unit.
        """
        self.end_stroke()
        self.editor.load(document)
        if self.edit_target != "unit":
            self.edit_target = "unit"
            self.notify(VIEW)
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
        """Make ``index`` the active colour slot.

        Choosing a colour while unpicking goes back to cross stitch; the
        backstitch tool stays on, so the next line gets the new colour.
        """
        if not 0 <= index < len(self.document.palette_sequences):
            return
        self.active_slot = index
        if self.tool == "unpick":
            self.tool = "cross"
        self.notify(VIEW)

    def set_mode(self, mode: Mode) -> None:
        """Switch between drawing (``"edit"``) and the whole band (``"preview"``)."""
        if mode not in MODES:
            raise ValueError(f"Unknown mode: {mode!r}")
        if mode != self.mode:
            self.end_stroke()
            self.mode = mode
            self.notify(VIEW)

    def set_tool(self, tool: Tool) -> None:
        """Choose the stitch tool: cross stitch, backstitch or unpick.

        Also switches to edit mode, as the tools draw (the whole band only shows).
        """
        if tool not in TOOLS:
            raise ValueError(f"Unknown tool: {tool!r}")
        if tool != self.tool or self.mode != "edit":
            self.end_stroke()
            self.tool = tool
            self.mode = "edit"
            self.notify(VIEW)

    @property
    def erase_tool(self) -> bool:
        """True when a plain click unpicks (the unpick tool is chosen)."""
        return self.tool == "unpick"

    def set_edit_target(self, target: EditTarget) -> None:
        """Draw in the unit, an end piece or a corner. Also switches to edit mode."""
        if target not in EDIT_TARGETS:
            raise ValueError(f"Unknown edit target: {target!r}")
        if target == self.edit_target and self.mode == "edit":
            return
        self.end_stroke()
        self.edit_target = target
        self.mode = "edit"
        self.notify(VIEW)

    def set_status(self, key: str | None, **values: object) -> None:
        """Show an i18n message to the user, or clear it with ``None``.

        Tuple or list values are taken as i18n keys: they are translated and
        joined with ", " when the message is shown.
        """
        self.status = None if key is None else (key, values)
        self.notify(STATUS)
