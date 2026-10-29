"""Rulers and the row/column popover.

The numbered buttons in ``#ruler-top`` and ``#ruler-left`` line up with the
grid's cells (``GridView`` calls ``update`` after each render). In the unit a
number opens ``#edge-popover``: a new row/column before or after, or remove
this one. The rows and columns the symmetry ties to it are highlighted on the
grid and named in the popover (``edge.also``). "More options …" opens chunk
5's rows and columns dialog (``panels.lines.open_lines_dialog``).

In an end piece or a corner the rulers are labels only; extra rows and
columns count outwards (+1, +2 …).

The buttons are built as one HTML string and use one click listener per
ruler, so a 100 x 100 unit costs two DOM calls, not 400.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from html import escape
from typing import Any, Literal

from pyscript import document

from kvale.core.editing import Axis, can_remove_grid_line
from kvale_web import i18n
from kvale_web.dom import Bindings, Element, by_id
from kvale_web.grid.scene import LineHighlight, ViewBox, also_changed, line_highlight, ruler_cells
from kvale_web.i18n import t
from kvale_web.state import DOCUMENT, LANGUAGE, VIEW, AppState

Action = Literal["before", "after", "remove"]

_POPOVER_HTML = """
<h3><span id="edge-title"></span>
  <button type="button" class="btn close" id="edge-close" data-i18n-aria-label="edge.close" data-i18n-title="edge.close"><svg class="icon"><use href="#i-x"/></svg></button></h3>
<button type="button" class="btn" id="edge-before" data-edge-action="before"><svg class="icon"><use href="#i-add"/></svg><span></span></button>
<button type="button" class="btn" id="edge-after" data-edge-action="after"><svg class="icon"><use href="#i-add"/></svg><span></span></button>
<button type="button" class="btn danger" id="edge-remove" data-edge-action="remove"><svg class="icon"><use href="#i-trash"/></svg><span></span></button>
<p class="note" id="edge-note" hidden></p>
<hr>
<button type="button" class="btn more" id="edge-more"><svg class="icon"><use href="#i-rows"/></svg><span data-i18n="edge.more">Flere valg …</span></button>
"""


def join_list(items: list[str]) -> str:
    """"a, b and c" in the current language."""
    if len(items) <= 1:
        return items[0] if items else ""
    return ", ".join(items[:-1]) + t("list.and") + items[-1]


def line_text(names: list[tuple[str, int]]) -> str:
    return join_list([t(key, n=n) for key, n in names])


class Rulers:
    def __init__(self, state: AppState) -> None:
        self.state = state
        self.editor: Element = by_id("editor")
        self.top: Element = by_id("ruler-top")
        self.left: Element = by_id("ruler-left")
        self.popover: Element = by_id("edge-popover")
        self.popover.innerHTML = _POPOVER_HTML
        self.title = by_id("edge-title")
        self.note = by_id("edge-note")
        self.buttons: dict[Action, Element] = {
            "before": by_id("edge-before"),
            "after": by_id("edge-after"),
            "remove": by_id("edge-remove"),
        }
        # The selected line (axis, index) while the popover is open.
        self.selected: tuple[Axis, int] | None = None
        self.highlight: LineHighlight | None = None
        # Called when the highlight changes, so the grid can redraw its overlay.
        self.on_highlight: Callable[[], None] = lambda: None
        self._key: tuple[object, ...] | None = None
        self._cell_size = 24
        self._pad = 1

        self.bindings = Bindings()
        self.bindings.on(self.top, "click", self.on_ruler_click)
        self.bindings.on(self.left, "click", self.on_ruler_click)
        self.bindings.on(by_id("edge-close"), "click", lambda _event: self.close())
        self.bindings.on(by_id("edge-more"), "click", self.on_more)
        for action, button in self.buttons.items():
            self.bindings.on(button, "click", functools.partial(self._on_apply, action))
            self.bindings.on(button, "mouseenter", functools.partial(self._on_preview, action))
            self.bindings.on(button, "focus", functools.partial(self._on_preview, action))
        self.bindings.on(self.popover, "mouseleave", lambda _event: self.preview(None))
        self.bindings.on(self.popover, "keydown", self.on_key)
        self.bindings.on(document, "pointerdown", self.on_outside)
        state.subscribe(self._on_change, DOCUMENT, VIEW, LANGUAGE)

    # Rulers --------------------------------------------------------------

    def clear(self) -> None:
        """No rulers (the whole band)."""
        if self._key != ():
            self.top.innerHTML = ""
            self.left.innerHTML = ""
            self._key = ()

    def update(self, box: ViewBox, cell_size: int, pad: int) -> None:
        """Rebuild the buttons when the view, cell size or selection changed."""
        self._cell_size, self._pad = cell_size, pad
        key = (box, cell_size, pad, i18n.current_language())
        if key != self._key:
            self._key = key
            self.top.innerHTML = self._html(box, "column", cell_size)
            self.left.innerHTML = self._html(box, "row", cell_size)
            self.top.style.paddingLeft = f"{pad}px"
            self.left.style.paddingTop = f"{pad}px"
        if self.selected is not None:
            self._place()

    def _html(self, box: ViewBox, axis: Axis, cell_size: int) -> str:
        size_property = "width" if axis == "column" else "height"
        title_key = "edge.col.title" if axis == "column" else "edge.row.title"
        parts = []
        for index, label, kind in ruler_cells(box, axis, cell_size):
            style = f"{size_property}:{cell_size}px"
            if box.target == "unit":
                expanded = "true" if self.selected == (axis, index) else "false"
                aria = escape(t(title_key, n=index + 1))
                parts.append(
                    f'<button type="button" style="{style}" data-axis="{axis}" data-index="{index}" '
                    f'aria-label="{aria}" title="{aria}" aria-expanded="{expanded}">{label}</button>'
                )
            else:
                extra = ' class="extra"' if kind == "extra" else ""
                parts.append(f'<button type="button" style="{style}"{extra} disabled tabindex="-1">{label}</button>')
        return "".join(parts)

    def on_ruler_click(self, event: Any) -> None:
        button = event.target.closest("button[data-axis]")
        if button is None or self.state.edit_target != "unit":
            return
        axis: Axis = "column" if str(button.dataset.axis) == "column" else "row"
        index = int(button.dataset.index)
        if self.selected == (axis, index):
            self.close()
        else:
            self.open(axis, index)

    # Popover -------------------------------------------------------------

    def open(self, axis: Axis, index: int) -> None:
        self._mark(self.selected, False)
        self.selected = (axis, index)
        self._mark(self.selected, True)
        self.popover.hidden = False
        self.render_popover()
        self._place()
        self.preview(None)

    def close(self) -> None:
        if self.selected is None:
            return
        self._mark(self.selected, False)
        self.selected = None
        self.highlight = None
        self.popover.hidden = True
        self.on_highlight()

    def _mark(self, line: tuple[Axis, int] | None, expanded: bool) -> None:
        """Set aria-expanded on the ruler button of ``line``."""
        if line is None:
            return
        ruler = self.top if line[0] == "column" else self.left
        button = ruler.querySelector(f'[data-index="{line[1]}"]')
        if button is not None:
            button.setAttribute("aria-expanded", "true" if expanded else "false")

    def on_outside(self, event: Any) -> None:
        """Close the popover on a press anywhere else (except the rulers)."""
        if self.selected is None:
            return
        target = event.target
        if self.popover.contains(target) or self.top.contains(target) or self.left.contains(target):
            return
        self.close()

    def _on_change(self, topic: str) -> None:
        state = self.state
        if self.selected is None:
            return
        if state.mode != "edit" or state.edit_target != "unit":
            self.close()
            return
        axis, index = self.selected
        size = state.document.unit_width if axis == "column" else state.document.unit_height
        if index >= size:
            self.selected = (axis, size - 1)
            self._mark(self.selected, True)
        self.render_popover()
        self.preview(None)

    def render_popover(self) -> None:
        if self.selected is None:
            return
        axis, index = self.selected
        prefix = "edge.col." if axis == "column" else "edge.row."
        self.title.textContent = t(prefix + "title", n=index + 1)
        self.buttons["before"].lastElementChild.textContent = t(prefix + "insertBefore")
        self.buttons["after"].lastElementChild.textContent = t(prefix + "insertAfter")
        self.buttons["remove"].lastElementChild.textContent = t(prefix + "remove")
        self.buttons["remove"].disabled = not can_remove_grid_line(self.state.document, axis, index)

    def preview(self, action: Action | None) -> None:
        """Highlight what ``action`` would change (the selected line and its partners when None)."""
        if self.selected is None:
            return
        axis, index = self.selected
        document = self.state.document
        if action in ("before", "after"):
            gap = index if action == "before" else index + 1
            self.highlight = line_highlight(document, axis, gap, insertion=True)
        else:
            self.highlight = line_highlight(document, axis, index, insertion=False)
        others = also_changed(document, axis, index, action or "remove")
        self.note.hidden = not others
        self.note.textContent = t("edge.also", list=line_text(others)) if others else ""
        self.on_highlight()

    def apply(self, action: Action) -> None:
        if self.selected is None:
            return
        axis, index = self.selected
        if action == "remove":
            result = self.state.edit(lambda editor: editor.change_grid_line(axis, index, insertion=False))
        else:
            gap = index if action == "before" else index + 1
            result = self.state.edit(lambda editor: editor.change_grid_line(axis, gap, insertion=True))
        if result.changed and action == "before" and self.selected is not None:
            # The selected line moved one step on.
            size = self.state.document.unit_width if axis == "column" else self.state.document.unit_height
            self._mark(self.selected, False)
            self.selected = (axis, min(index + 1, size - 1))
            self._mark(self.selected, True)
            self.render_popover()
            self._place()
            self.preview(action)
        elif result.changed:
            self.preview(action)

    def _on_apply(self, action: Action, _event: Any) -> None:
        self.apply(action)

    def _on_preview(self, action: Action, _event: Any) -> None:
        self.preview(action)

    def on_more(self, _event: Any) -> None:
        from kvale_web.panels import lines

        self.close()
        lines.open_lines_dialog()

    def on_key(self, event: Any) -> None:
        if str(event.key) == "Escape":
            self.close()

    def _place(self) -> None:
        """Put the popover under the selected ruler number."""
        if self.selected is None:
            return
        axis, index = self.selected
        ruler = self.top if axis == "column" else self.left
        button = ruler.querySelector(f'[data-index="{index}"]')
        if button is None:
            return
        editor = self.editor.getBoundingClientRect()
        rect = button.getBoundingClientRect()
        width = float(self.popover.offsetWidth)
        if axis == "column":
            left = float(rect.left - editor.left) + float(rect.width) / 2 - width / 2
            left = max(0.0, min(float(self.editor.offsetWidth) - width, left))
            top = float(rect.bottom - editor.top) + 4
        else:
            left = float(rect.right - editor.left) + 4
            top = float(rect.bottom - editor.top)
        self.popover.style.left = f"{left}px"
        self.popover.style.top = f"{top}px"
