"""The "Drawing in" bar, the end-piece / corner panel and the reset confirm.

- ``#target-bar``: buttons in ``#target-seg`` (the unit and the four ends) and
  ``#corner-seg`` (the four corners), with a small band icon and a dot on the
  pieces that change anything. A click calls ``state.set_edit_target``.
- ``#end-panel`` (while an end or a corner is edited): what it is, a summary
  of its changes, the extra rows/columns stepper (ends only: a corner follows
  its two ends), Reset and Done.
- ``#reset-dialog``: "Reset this end/corner?" naming what will be lost (owner
  decision 2). Cancel has focus. Undo can bring the piece back afterwards.
"""

from __future__ import annotations

from html import escape
from typing import Any

import js
from pyodide.ffi import to_js

from kvale.core.editing import CORNERS, EDGES, Edge, EditTarget, EndPiece
from kvale_web.dom import Bindings, by_id
from kvale_web.grid.scene import (
    MAX_EXTENSION,
    SHORT_NAMES,
    as_edge,
    changed_pieces,
    is_corner,
    piece_summary,
    reset_loss,
    sides_of,
    title_key,
)
from kvale_web.i18n import t
from kvale_web.state import DOCUMENT, EDIT_TARGETS, LANGUAGE, TARGET_LABEL_KEYS, VIEW, AppState

_PANEL_HTML = """
<div class="who">
  <svg id="end-icon" aria-hidden="true"></svg>
  <div>
    <h3 id="end-title"></h3>
    <p><span id="end-where"></span> <span id="end-explain"></span></p>
    <p class="endsummary" id="end-summary"></p>
  </div>
</div>
<div class="ext" id="end-ext-wrap">
  <label for="end-ext" id="end-ext-label"></label>
  <div class="stepper">
    <button type="button" id="end-ext-less" data-i18n-aria-label="step.less">−</button>
    <input id="end-ext" type="number" min="0" max="50" value="0" inputmode="numeric">
    <button type="button" id="end-ext-more" data-i18n-aria-label="step.more">+</button>
  </div>
  <small data-i18n="end.extra.hint">Gir plass til en kant utenfor rapporten</small>
</div>
<p class="cornersize" id="corner-size" data-i18n="corner.size" hidden></p>
<div class="actions">
  <button type="button" class="btn danger-text" id="end-reset" data-i18n-title="end.reset.hint"><svg class="icon"><use href="#i-reset"/></svg><span data-i18n="end.reset">Tilbakestill</span></button>
  <button type="button" class="btn primary" id="end-done" data-i18n-title="end.done.hint"><svg class="icon"><use href="#i-check"/></svg><span data-i18n="end.done">Ferdig</span></button>
</div>
"""

_DIALOG_HTML = """
<form method="dialog" class="dlg">
  <header><h2 id="reset-title"></h2></header>
  <div class="content" id="reset-body">
    <p class="effect" id="reset-what"></p>
    <ul class="losslist" id="reset-loss"></ul>
    <p class="caption" style="margin:0" data-i18n="end.confirm.undo"></p>
  </div>
  <footer>
    <button type="submit" class="btn" value="cancel" id="reset-cancel" autofocus data-i18n="end.confirm.cancel"></button>
    <button type="submit" class="btn danger" value="ok" id="reset-ok"><svg class="icon"><use href="#i-reset"/></svg><span data-i18n="end.confirm.ok"></span></button>
  </footer>
</form>
"""


def target_icon(target: EditTarget, width: int = 30, height: int = 20, extra: str = 'class="ticon"') -> str:
    """A tiny band of 5 x 2 repeats with the piece ``target`` covers filled in."""
    columns, rows = 5, 2
    cell_w, cell_h = (width - 2) / columns, (height - 2) / rows
    sides = sides_of(target)

    def on_side(edge: str, c: int, r: int) -> bool:
        return {
            "left": c == 0,
            "right": c == columns - 1,
            "top": r == 0,
            "bottom": r == rows - 1,
        }[edge]

    parts = [f'<svg {extra} viewBox="0 0 {width} {height}" aria-hidden="true">']
    for r in range(rows):
        for c in range(columns):
            on = (c == 2 and r == 0) if target == "unit" else all(on_side(e, c, r) for e in sides)
            parts.append(
                f'<rect x="{1 + c * cell_w + 0.6:.2f}" y="{1 + r * cell_h + 0.6:.2f}" '
                f'width="{cell_w - 1.2:.2f}" height="{cell_h - 1.2:.2f}" rx="1" '
                f'fill="currentColor" fill-opacity="{1 if on else 0.22}"/>'
            )
    parts.append("</svg>")
    return "".join(parts)


class TargetBar:
    def __init__(self, state: AppState) -> None:
        self.state = state
        self.bar = by_id("target-bar")
        self.target_seg = by_id("target-seg")
        self.corner_seg = by_id("corner-seg")
        self.end_panel = by_id("end-panel")
        self.end_panel.innerHTML = _PANEL_HTML
        self.reset_dialog = by_id("reset-dialog")
        self.reset_dialog.innerHTML = _DIALOG_HTML
        self.reset_dialog.setAttribute("aria-labelledby", "reset-title")
        self.reset_dialog.setAttribute("aria-describedby", "reset-body")
        self.ext_input = by_id("end-ext")
        self._reset_target: EndPiece | None = None
        self._shown: EditTarget | None = None

        self.bindings = Bindings()
        self.bindings.on(self.target_seg, "click", self.on_target_click)
        self.bindings.on(self.corner_seg, "click", self.on_target_click)
        self.bindings.on(by_id("end-ext-less"), "click", lambda _event: self.step_extension(-1))
        self.bindings.on(by_id("end-ext-more"), "click", lambda _event: self.step_extension(1))
        self.bindings.on(self.ext_input, "change", self.on_extension_input)
        self.bindings.on(by_id("end-reset"), "click", lambda _event: self.open_reset())
        self.bindings.on(by_id("end-done"), "click", lambda _event: state.set_edit_target("unit"))
        self.bindings.on(self.reset_dialog, "close", self.on_reset_close)
        state.subscribe(lambda _topic: self.render(), DOCUMENT, VIEW, LANGUAGE)
        self.bar.hidden = False
        self.render()

    # Actions -------------------------------------------------------------

    def on_target_click(self, event: Any) -> None:
        button = event.target.closest("button[data-target]")
        if button is None:
            return
        value = str(button.dataset.target)
        for known in EDIT_TARGETS:
            if known == value:
                self.state.set_edit_target(known)

    def _edge(self) -> Edge | None:
        target = self.state.edit_target
        return as_edge(target)

    def set_extension(self, value: int) -> None:
        edge = self._edge()
        if edge is None:
            return
        value = max(0, min(MAX_EXTENSION, value))
        self.state.edit(lambda editor: editor.set_end_piece_extension(edge, value))
        self.ext_input.value = str(self.state.document.extension_of(edge))

    def step_extension(self, delta: int) -> None:
        edge = self._edge()
        if edge is not None:
            self.set_extension(self.state.document.extension_of(edge) + delta)

    def on_extension_input(self, _event: Any) -> None:
        try:
            value = int(float(str(self.ext_input.value)))
        except ValueError:
            value = 0
        self.set_extension(value)

    def open_reset(self) -> None:
        target = self.state.edit_target
        if target == "unit" or piece_summary(self.state.document, target).empty:
            return
        self._reset_target = target
        self.render_reset()
        self.reset_dialog.returnValue = ""
        self.reset_dialog.showModal()
        by_id("reset-cancel").focus()

    def on_reset_close(self, _event: Any) -> None:
        piece = self._reset_target
        self._reset_target = None
        if str(self.reset_dialog.returnValue) != "ok" or piece is None:
            return
        result = self.state.edit(lambda editor: editor.reset_end_piece(piece))
        if result.changed:
            self.state.set_status("end.resetDone", name=(title_key(piece),))

    # Rendering -----------------------------------------------------------

    def render(self) -> None:
        state = self.state
        target = state.edit_target
        changed = changed_pieces(state.document)
        self.target_seg.innerHTML = self._buttons(("unit", *EDGES), target, changed)
        self.corner_seg.innerHTML = self._buttons(CORNERS, target, changed)
        self.render_panel()
        if self._reset_target is not None and self.reset_dialog.open:
            self.render_reset()

    def _buttons(self, targets: tuple[EditTarget, ...], current: EditTarget, changed: frozenset[EndPiece]) -> str:
        parts = []
        for target in targets:
            if target == "unit":
                title = t("target.unit.hint")
            elif is_corner(target):
                title = f"{t(title_key(target))} – {t('target.corner.hint')}"
            else:
                title = t("target.edge.hint")
            dot = ""
            if target in changed:
                note = escape(t("target.changed"))
                dot = f'<i class="changed" title="{note}"></i><span class="sr-only">({note})</span>'
            pressed = "true" if target == current else "false"
            parts.append(
                f'<button type="button" data-target="{target}" aria-pressed="{pressed}" title="{escape(title)}">'
                f"{target_icon(target)}<span>{escape(t(TARGET_LABEL_KEYS[target]))}</span>{dot}</button>"
            )
        return "".join(parts)

    def render_panel(self) -> None:
        target = self.state.edit_target
        panel = self.end_panel
        panel.hidden = target == "unit"
        if target == "unit":
            self._shown = None
            return
        piece: EndPiece = target
        corner = is_corner(target)
        short = SHORT_NAMES[target]
        icon = by_id("end-icon")
        icon.outerHTML = target_icon(target, 46, 30, 'id="end-icon"')
        by_id("end-icon").style.color = "var(--accent)"
        by_id("end-title").textContent = t(title_key(target))
        by_id("end-where").textContent = t(("corner.where." if corner else "end.where.") + short)
        by_id("end-explain").textContent = t("corner.explain" if corner else "end.explain")
        by_id("end-ext-wrap").hidden = corner
        by_id("corner-size").hidden = not corner
        horizontal = target in ("left", "right")
        by_id("end-ext-label").textContent = t("end.extra.cols" if horizontal else "end.extra.rows")
        if not corner:
            self.ext_input.value = str(self.state.document.extension_of(target))
        summary = piece_summary(self.state.document, piece)
        if summary.empty:
            text = t("corner.summary.none" if corner else "end.summary.none")
        else:
            text = t("end.summary", added=summary.added, removed=summary.removed, lines=summary.lines)
        by_id("end-summary").textContent = text
        by_id("end-reset").disabled = summary.empty
        if self._shown != target:
            self._shown = target
            panel.scrollIntoView(to_js({"block": "nearest"}, dict_converter=js.Object.fromEntries))

    def render_reset(self) -> None:
        piece = self._reset_target
        if piece is None:
            return
        corner = is_corner(piece)
        loss = reset_loss(self.state.document, piece)
        summary = loss.summary
        by_id("reset-title").textContent = t("corner.confirm.title" if corner else "end.confirm.title")
        name = f"<strong>{escape(t(title_key(piece)))}</strong>"
        body_key = "corner.confirm.body" if corner else "end.confirm.body"
        by_id("reset-what").innerHTML = escape(t(body_key, name="\0")).replace("\0", name)
        items = []
        if summary.added or summary.removed or summary.lines:
            items.append(t("end.confirm.changes", added=summary.added, removed=summary.removed, lines=summary.lines))
        if summary.extension:
            key = "end.confirm.extraCols" if piece in ("left", "right") else "end.confirm.extraRows"
            items.append(t(key, n=summary.extension))
        if loss.corner_stitches:
            items.append(t("end.confirm.corners", n=loss.corner_stitches))
        by_id("reset-loss").innerHTML = "".join(f"<li>{escape(item)}</li>" for item in items)
