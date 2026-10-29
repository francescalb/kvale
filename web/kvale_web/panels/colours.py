"""The Colours card: colour slots, "Add colour", the colour change toggle and
the fabric (background) colour.

- ``#colour-slots``: one row per slot: number, a bar with the slot's colours
  (a split swatch for a sequence), "DMC 321" or "3 colours in turn", and a
  pencil button that opens the colour dialog. A click selects the slot.
- ``#colour-actions``: "Add colour" opens the thread picker first; the chosen
  thread becomes a new slot, which is then selected.
- ``#colour-sequence-toggle``: ``Editor.set_use_palette_sequence``.
- ``#background-row``: ``Editor.set_background``. Dragging in the colour
  wheel is one undo step.

The card re-renders from ``state.document`` on every ``DOCUMENT``
notification, so undo/redo and opening a file update it for free.
"""

from __future__ import annotations

import functools
from typing import Any

from kvale_web.dom import Bindings, by_id, clear, create
from kvale_web.i18n import t
from kvale_web.panels.colour_dialog import ColourDialog
from kvale_web.panels.colour_model import slot_colours
from kvale_web.panels.labels import full_text, slot_text
from kvale_web.panels.thread_picker import ThreadPicker
from kvale_web.state import DOCUMENT, LANGUAGE, VIEW, AppState


class ColoursPanel:
    def __init__(self, state: AppState, picker: ThreadPicker, dialog: ColourDialog) -> None:
        self.state = state
        self.picker = picker
        self.dialog = dialog
        self.slots = by_id("colour-slots")
        self.use_sequence = by_id("use-sequence")
        self.background = by_id("background-input")
        self.slot_bindings = Bindings()  # rebuilt with the slots
        self._background_open = False

        self.bindings = Bindings()
        self.bindings.on(by_id("add-colour"), "click", self.on_add)
        self.bindings.on(self.use_sequence, "click", self.on_use_sequence)
        self.bindings.on(self.background, "input", self.on_background_input)
        self.bindings.on(self.background, "change", self.on_background_change)
        state.subscribe(lambda _topic: self.render(), DOCUMENT, VIEW, LANGUAGE)
        self.render()

    # Events ------------------------------------------------------------

    def on_select(self, index: int, _event: Any) -> None:
        self.state.select_slot(index)

    def on_edit(self, index: int, _event: Any) -> None:
        self.dialog.open(index)

    def on_add(self, _event: Any) -> None:
        self.picker.open(None, self.on_added)

    def on_added(self, colour: str, ref: str | None) -> None:
        result = self.state.edit(lambda editor: editor.add_colour(colour, [ref]))
        if result.changed:
            self.state.select_slot(len(self.state.document.palette_sequences) - 1)

    def on_use_sequence(self, _event: Any) -> None:
        enabled = not self.state.document.use_palette_sequence
        self.state.edit(lambda editor: editor.set_use_palette_sequence(enabled))

    def on_background_input(self, _event: Any) -> None:
        # Every step of a drag in the colour wheel shows at once; the whole
        # drag is one undo step, closed by the "change" event.
        if not self._background_open:
            self.state.begin_stroke()
            self._background_open = True
        colour = str(self.background.value).lower()
        self.state.edit(lambda editor: editor.set_background(colour))

    def on_background_change(self, event: Any) -> None:
        if not self._background_open:
            self.on_background_input(event)
        self._background_open = False
        self.state.end_stroke()

    # Drawing -----------------------------------------------------------

    def render(self) -> None:
        doc = self.state.document
        self.slot_bindings.destroy()
        clear(self.slots)
        for index, infos in enumerate(slot_colours(doc)):
            active = index == self.state.active_slot
            row = create("div", class_name="slot", parent=self.slots)
            details = ", ".join(full_text(info) for info in infos)
            select = create(
                "button",
                class_name="slot-select",
                attrs={
                    "type": "button",
                    "aria-pressed": "true" if active else "false",
                    "title": "\n".join(full_text(info) for info in infos),
                    "aria-label": f"{t('colours.slot', n=index + 1)} – {details}",
                    "data-slot": str(index),
                },
                parent=row,
            )
            create("span", class_name="slot-num", text=f"#{index + 1}", parent=select)
            body = create("span", class_name="slot-body", parent=select)
            bar = create("span", class_name="swatchbar", parent=body)
            for info in infos:
                create("i", parent=bar).style.background = info.hex_colour
            meta = create("span", class_name="slot-meta", parent=body)
            create("span", text=slot_text(infos), parent=meta)
            create("span", text=f"✓ {t('colours.selected')}" if active else "", parent=meta)
            edit_label = t("colours.edit", n=index + 1)
            edit = create(
                "button",
                class_name="btn slot-edit icon-only",
                attrs={"type": "button", "title": edit_label, "aria-label": edit_label},
                parent=row,
            )
            edit.innerHTML = '<svg class="icon"><use href="#i-pencil"/></svg>'
            self.slot_bindings.on(select, "click", functools.partial(self.on_select, index))
            self.slot_bindings.on(select, "dblclick", functools.partial(self.on_edit, index))
            self.slot_bindings.on(edit, "click", functools.partial(self.on_edit, index))

        self.use_sequence.setAttribute("aria-checked", "true" if doc.use_palette_sequence else "false")
        by_id("background-swatch").style.backgroundColor = doc.background
        by_id("background-hex").textContent = doc.background
        if not self._background_open:
            self.background.value = doc.background
