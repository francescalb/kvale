"""The rows and columns dialog: ``<dialog id="lines-dialog">``.

Add or remove a row or column: at the top, at the bottom, at the far left or
right, or by number. The dialog shows which rows and columns the symmetry
takes along (marked in a preview of the repeat), the size the repeat
becomes, and refuses to remove the last row or column. "Add"/"Remove"
applies it as one undo step (``Editor.change_grid_line``). The logic is in
``lines_model``.

Other views open it with ``open_lines_dialog()`` (see web/README.md):

- ``open_lines_dialog()``: as last used (first time: add at the bottom);
- ``open_lines_dialog("row", 4)``: row 5 (0-based index 4) chosen, "Add";
- ``open_lines_dialog("column", 0, remove=True)``: column 1 chosen, "Remove".
"""

from __future__ import annotations

from typing import Any

from kvale.core.editing import Axis
from kvale.core.symmetry import expand_marks
from kvale_web.dom import Bindings, by_id, query_all
from kvale_web.i18n import t
from kvale_web.panels.labels import join_list
from kvale_web.panels.lines_model import LinesChoice, lines_effect
from kvale_web.state import DOCUMENT, LANGUAGE, AppState

_dialog: LinesDialog | None = None
# Preview colours: new lines (blue) and lines that go (red), as in the design.
_ADD = "#2f5d9e"
_REMOVE = "#b3261e"


class LinesDialog:
    def __init__(self, state: AppState) -> None:
        global _dialog
        self.state = state
        self.dialog = by_id("lines-dialog")
        self.number = by_id("lines-number")
        self.apply = by_id("lines-apply")
        self.choice = LinesChoice()
        self.bindings = Bindings()
        for button in query_all("#lines-action [data-action]"):
            self.bindings.on(button, "click", self.on_action)
        for button in query_all("#lines-places [data-place]"):
            self.bindings.on(button, "click", self.on_place)
        self.bindings.on(by_id("lines-less"), "click", lambda _e: self.step(-1))
        self.bindings.on(by_id("lines-more"), "click", lambda _e: self.step(1))
        self.bindings.on(self.number, "change", self.on_number)
        self.bindings.on(self.number, "keydown", self.on_number_key)
        self.bindings.on(self.dialog, "close", self.on_close)
        state.subscribe(lambda _topic: self.render() if self.dialog.open else None, DOCUMENT, LANGUAGE)
        _dialog = self

    def open(self, axis: Axis | None = None, index: int | None = None, *, remove: bool = False) -> None:
        """Show the dialog; with ``axis`` and ``index`` (0-based) that row/column is chosen."""
        if axis is not None:
            self.choice = LinesChoice(
                insertion=not remove,
                place="column" if axis == "column" else "row",
                number=(index or 0) + 1,
            )
        self.dialog.returnValue = ""
        self.render()
        self.dialog.showModal()

    # Events ------------------------------------------------------------

    def on_action(self, event: Any) -> None:
        self.choice.insertion = str(event.currentTarget.dataset.action) == "add"
        self.render()

    def on_place(self, event: Any) -> None:
        place = str(event.currentTarget.dataset.place)
        if place in ("top_row", "bottom_row", "first_column", "last_column", "row", "column"):
            self.choice.place = place  # type: ignore[assignment]
        self.render()

    def step(self, delta: int) -> None:
        self.choice.number += delta
        self.render()

    def on_number(self, _event: Any) -> None:
        try:
            self.choice.number = round(float(str(self.number.value)))
        except ValueError:
            pass
        self.render()

    def on_number_key(self, event: Any) -> None:
        if event.key == "Enter":
            event.preventDefault()
            self.on_number(event)

    def on_close(self, _event: Any) -> None:
        if self.dialog.returnValue != "ok":
            return
        doc = self.state.document
        if not lines_effect(doc, self.choice).allowed:
            self.state.set_status("lines.cantRemove")
            return
        axis, index = self.choice.line(doc)
        insertion = self.choice.insertion
        self.state.edit(lambda editor: editor.change_grid_line(axis, index, insertion=insertion))

    # Drawing -----------------------------------------------------------

    def render(self) -> None:
        doc = self.state.document
        choice = self.choice
        choice.clamp(doc)
        effect = lines_effect(doc, choice)
        for button in query_all("#lines-action [data-action]"):
            on = (str(button.dataset.action) == "add") == choice.insertion
            button.setAttribute("aria-pressed", "true" if on else "false")
        for button in query_all("#lines-places [data-place]"):
            button.setAttribute("aria-pressed", "true" if button.dataset.place == choice.place else "false")

        by_id("lines-number-wrap").hidden = not choice.numbered
        highest = choice.max_number(doc)
        self.number.max = str(highest)
        self.number.value = str(choice.number)
        by_id("lines-number-range").textContent = f"(1–{highest})"

        text = by_id("lines-effect")
        text.className = "effect" if effect.allowed else "effect warn"
        if effect.allowed:
            names = join_list([t(key, n=n) for key, n in effect.labels()])
            message = t("lines.effect.add" if effect.insertion else "lines.effect.remove", list=names)
            text.textContent = f"{message} {t('lines.result', w=effect.new_width, h=effect.new_height)}"
            if effect.count > 1:
                note = text.ownerDocument.createElement("small")
                note.textContent = t("lines.symNote")
                text.appendChild(note)
        else:
            text.textContent = t("lines.cantRemove")
        self.apply.textContent = t("lines.apply.add" if effect.insertion else "lines.apply.remove")
        self.apply.disabled = not effect.allowed
        self.render_preview(effect.insertion, effect.columns, effect.rows)

    def render_preview(self, insertion: bool, columns: tuple[int, ...], rows: tuple[int, ...]) -> None:
        """The repeat with its stitches, and the lines that would be added or removed."""
        doc = self.state.document
        cell = max(6, min(16, 260 // max(doc.unit_width, doc.unit_height)))
        width, height = doc.unit_width * cell, doc.unit_height * cell
        palette = doc.palette
        parts = [f'<rect x="0" y="0" width="{width}" height="{height}" fill="{doc.background}"/>']
        for mark in expand_marks(doc.motif, doc.unit_width, doc.unit_height, doc.symmetry):
            colour = palette[mark.colour_slot % len(palette)]
            parts.append(
                f'<rect x="{mark.x * cell}" y="{mark.y * cell}" width="{cell}" height="{cell}" fill="{colour}"/>'
            )
        parts += [f'<path d="M{x * cell} 0V{height}" stroke="rgba(70,50,30,.2)"/>' for x in range(doc.unit_width + 1)]
        parts += [f'<path d="M0 {y * cell}H{width}" stroke="rgba(70,50,30,.2)"/>' for y in range(doc.unit_height + 1)]
        if insertion:
            parts += [
                f'<rect class="line-new" x="{gap * cell - 2}" y="-4" width="4" height="{height + 8}" rx="2" fill="{_ADD}"/>'
                for gap in columns
            ]
            parts += [
                f'<rect class="line-new" x="-4" y="{gap * cell - 2}" width="{width + 8}" height="4" rx="2" fill="{_ADD}"/>'
                for gap in rows
            ]
        else:
            parts += [
                f'<rect class="line-gone" x="{x * cell}" y="0" width="{cell}" height="{height}" fill="{_REMOVE}" fill-opacity=".45"/>'
                for x in columns
            ]
            parts += [
                f'<rect class="line-gone" x="0" y="{y * cell}" width="{width}" height="{cell}" fill="{_REMOVE}" fill-opacity=".45"/>'
                for y in rows
            ]
        svg = by_id("lines-preview")
        svg.setAttribute("viewBox", f"-5 -5 {width + 10} {height + 10}")
        svg.setAttribute("width", str(width + 10))
        svg.setAttribute("height", str(height + 10))
        svg.innerHTML = "".join(parts)


def open_lines_dialog(axis: Axis | None = None, index: int | None = None, *, remove: bool = False) -> None:
    """Open the rows and columns dialog, if the panels are mounted.

    ``axis`` ("row" or "column") and ``index`` (0-based) choose that line; for
    an insertion the index is the gap before which the new line goes.
    ``remove=True`` starts on "Remove" instead of "Add".
    """
    if _dialog is not None:
        _dialog.open(axis, index, remove=remove)
