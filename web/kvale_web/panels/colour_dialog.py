"""The colour slot dialog: ``<dialog id="colour-dialog">``.

For one slot: the number of thread colours (1-24), the parts, quick threads,
"Find a thread …" (opens the thread picker), own colour (colour wheel, or a
typed "#rrggbb" / "r, g, b"), and how the colour changes along the band.
"Apply" stores the sequence with each colour's thread reference in one undo
step (``Editor.set_colour_sequence``); "Cancel" changes nothing.
"""

from __future__ import annotations

import functools
import html
from typing import Any

from kvale_web.dom import Bindings, by_id, clear, create
from kvale_web.i18n import t
from kvale_web.panels.colour_model import (
    QUICK_THREADS,
    ColourDraft,
    band_preview,
    colour_info,
    parse_colour,
    text_colour_on,
)
from kvale_web.panels.labels import full_text
from kvale_web.panels.thread_picker import ThreadPicker
from kvale_web.state import DOCUMENT, LANGUAGE, AppState
from kvale.core.threads import find_thread


class ColourDialog:
    def __init__(self, state: AppState, picker: ThreadPicker) -> None:
        self.state = state
        self.picker = picker
        self.dialog = by_id("colour-dialog")
        self.count = by_id("colour-dialog-count")
        self.parts = by_id("colour-dialog-parts")
        self.threads = by_id("colour-dialog-threads")
        self.custom = by_id("colour-dialog-custom")
        self.hex = by_id("colour-dialog-hex")
        self.draft: ColourDraft | None = None
        self.part_bindings = Bindings()  # rebuilt with the parts and quick threads

        self.bindings = Bindings()
        self.bindings.on(by_id("colour-dialog-less"), "click", lambda _e: self.resize(-1))
        self.bindings.on(by_id("colour-dialog-more"), "click", lambda _e: self.resize(1))
        self.bindings.on(self.count, "change", self.on_count)
        self.bindings.on(self.count, "keydown", self.on_count_key)
        self.bindings.on(by_id("colour-dialog-find"), "click", self.on_find)
        self.bindings.on(self.custom, "input", self.on_custom)
        self.bindings.on(self.hex, "change", self.on_hex)
        self.bindings.on(self.hex, "keydown", self.on_hex_key)
        self.bindings.on(self.dialog, "close", self.on_close)
        state.subscribe(lambda _topic: self.render() if self.dialog.open else None, DOCUMENT, LANGUAGE)

    def open(self, slot: int) -> None:
        """Show the dialog for colour slot ``slot`` (0-based)."""
        if not 0 <= slot < len(self.state.document.palette_sequences):
            return
        self.draft = ColourDraft.from_document(self.state.document, slot)
        self.dialog.returnValue = ""
        self.render()
        self.dialog.showModal()

    # Events ------------------------------------------------------------

    def resize(self, step: int) -> None:
        if self.draft is not None:
            self.draft.resize(len(self.draft.colours) + step)
            self.render()

    def on_count(self, _event: Any) -> None:
        if self.draft is None:
            return
        try:
            length = round(float(str(self.count.value)))
        except ValueError:
            length = len(self.draft.colours)
        self.draft.resize(length)
        self.render()

    def on_count_key(self, event: Any) -> None:
        if event.key == "Enter":  # apply the number; do not submit the form
            event.preventDefault()
            self.on_count(event)

    def on_part(self, part: int, _event: Any) -> None:
        if self.draft is not None:
            self.draft.select(part)
            self.render()

    def on_quick(self, ref: str, _event: Any) -> None:
        thread = find_thread(ref)
        if self.draft is not None and thread is not None:
            self.draft.set_colour(thread.hex_colour, ref)
            self.render()

    def on_find(self, _event: Any) -> None:
        if self.draft is not None:
            self.picker.open(self.draft.current.ref, self.on_picked)

    def on_picked(self, colour: str, ref: str | None) -> None:
        if self.draft is not None:
            self.draft.set_colour(colour, ref)
            self.render()

    def on_custom(self, _event: Any) -> None:
        if self.draft is not None:
            self.draft.set_colour(str(self.custom.value), None)
            self.render()

    def on_hex(self, _event: Any) -> None:
        colour = parse_colour(str(self.hex.value))
        if colour is None:
            self.hex.setAttribute("aria-invalid", "true")
            return
        self.hex.removeAttribute("aria-invalid")
        if self.draft is not None:
            current = self.draft.current
            if colour != current.hex_colour.lower() or current.is_thread:
                self.draft.set_colour(colour, None)
            self.render()

    def on_hex_key(self, event: Any) -> None:
        if event.key == "Enter":
            event.preventDefault()
            self.on_hex(event)

    def on_close(self, _event: Any) -> None:
        draft = self.draft
        self.draft = None
        if self.dialog.returnValue != "ok" or draft is None:
            return
        if draft.slot >= len(self.state.document.palette_sequences):
            return
        self.state.edit(
            lambda editor: editor.set_colour_sequence(draft.slot, draft.colours, draft.refs)
        )
        self.state.select_slot(draft.slot)

    # Drawing -----------------------------------------------------------

    def render(self) -> None:
        draft = self.draft
        if draft is None:
            return
        doc = self.state.document
        by_id("colour-dialog-title").textContent = t("dialog.title", n=draft.slot + 1)
        by_id("colour-dialog-bar").innerHTML = "".join(
            f'<i style="background:{html.escape(colour)}"></i>' for colour in draft.colours
        )
        self.count.value = str(len(draft.colours))

        self.part_bindings.destroy()
        clear(self.parts)
        for index, info in enumerate(draft.infos()):
            label = full_text(info)
            button = create(
                "button",
                class_name="part",
                text=str(index + 1),
                attrs={
                    "type": "button",
                    "title": label,
                    "aria-label": f"{t('dialog.part', n=index + 1)} – {label}",
                    "aria-pressed": "true" if index == draft.part else "false",
                },
                parent=self.parts,
            )
            button.style.background = info.hex_colour
            button.style.color = text_colour_on(info.hex_colour)
            self.part_bindings.on(button, "click", functools.partial(self.on_part, index))

        current = draft.current
        by_id("colour-dialog-pick-label").textContent = (
            f"{t('dialog.pick', n=draft.part + 1)} – {full_text(current)}"
        )
        clear(self.threads)
        for ref in QUICK_THREADS:
            thread = find_thread(ref)
            if thread is None:
                continue
            label = full_text(colour_info(thread.hex_colour, ref))
            button = create(
                "button",
                class_name="thread",
                attrs={
                    "type": "button",
                    "title": label,
                    "aria-label": label,
                    "aria-pressed": "true" if current.ref == ref else "false",
                },
                parent=self.threads,
            )
            button.style.background = thread.hex_colour
            self.part_bindings.on(button, "click", functools.partial(self.on_quick, ref))

        self.custom.value = current.hex_colour
        by_id("colour-dialog-custom-chip").style.background = current.hex_colour
        self.hex.value = current.hex_colour
        self.hex.removeAttribute("aria-invalid")

        repeats = band_preview(draft.colours, doc.repeats_x, doc.use_palette_sequence)
        by_id("colour-dialog-repeats").innerHTML = "".join(
            f'<span style="background:{colour};color:{text_colour_on(colour)}">{index + 1}</span>'
            for index, colour in enumerate(repeats)
        )
        by_id("colour-dialog-off-note").hidden = doc.use_palette_sequence
