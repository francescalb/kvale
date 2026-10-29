"""The Colours card (chunk 5): colour slots, add colour, colour change toggle
and the fabric (background) colour.

Belongs here: the slot list in ``#colour-slots`` (number, swatch bar of the
sequence, "DMC 321" via ``thread.code``, "Change" button that opens the
colour dialog), ``#colour-actions`` ("Add colour" opens the thread picker),
``#colour-sequence-toggle`` (``Editor.set_use_palette_sequence``) and
``#background-row`` (``Editor.set_background``); strings ``colours.*``.

For now: ``ColoursPanel`` shows one round swatch per slot, as before the
redesign. A click calls ``state.select_slot``.

Each panel re-syncs its controls from ``state.document`` on every
``DOCUMENT`` notification, so undo/redo and opening a file update it for
free. Panels that rebuild elements must call ``Bindings.destroy()`` on the
old ones.
"""

from __future__ import annotations

import functools
from typing import Any

from kvale_web.dom import Bindings, by_id, clear, create
from kvale_web.i18n import t
from kvale_web.state import DOCUMENT, LANGUAGE, VIEW, AppState


class ColoursPanel:
    def __init__(self, state: AppState) -> None:
        self.state = state
        self.slots = by_id("colour-slots")
        self.container = create("div", class_name="swatches", parent=self.slots)
        self.swatch_bindings = Bindings()  # rebuilt with the swatches
        state.subscribe(lambda _topic: self.render(), DOCUMENT, VIEW, LANGUAGE)
        self.render()

    def on_swatch(self, index: int, _event: Any) -> None:
        self.state.select_slot(index)

    def render(self) -> None:
        self.swatch_bindings.destroy()
        clear(self.container)
        for index, colour in enumerate(self.state.document.palette):
            active = index == self.state.active_slot
            label = t("colours.slot", n=index + 1)
            button = create(
                "button",
                class_name="swatch",
                text=str(index + 1),
                attrs={
                    "type": "button",
                    "title": f"{label} {colour}",
                    "aria-label": label,
                    "aria-pressed": "true" if active else "false",
                },
                parent=self.container,
            )
            button.style.setProperty("--swatch", colour)
            self.swatch_bindings.on(button, "click", functools.partial(self.on_swatch, index))
