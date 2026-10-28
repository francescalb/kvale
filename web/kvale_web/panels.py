"""Side panels (chunk 5 extends this): grid settings, symmetry, colour slots,
sequence editor and background colour.

Each panel is a class that takes the ``AppState`` and binds to markup that is
already in ``index.html`` (looked up by id or class). It subscribes to the
topics it shows and re-syncs its controls from ``state.document`` on every
``DOCUMENT`` notification, so undo/redo and opening a file update it for free.
Panels that rebuild elements must call ``Bindings.destroy()`` on the old ones.

So far: ``PalettePanel`` (colour swatches and the eraser toggle) and
``SymmetryPanel`` (one checkbox per symmetry operation).
"""

from __future__ import annotations

import functools
from typing import Any

from kvale.core.symmetry import SQUARE_ONLY_OPERATIONS
from kvale_web.dom import Bindings, by_id, clear, create, query_all
from kvale_web.i18n import t
from kvale_web.state import DOCUMENT, LANGUAGE, VIEW, AppState


class PalettePanel:
    """Colour slot swatches in ``#palette`` and the ``#erase`` checkbox."""

    def __init__(self, state: AppState) -> None:
        self.state = state
        self.container = by_id("palette")
        self.erase_box = by_id("erase")
        self.bindings = Bindings()
        self.swatch_bindings = Bindings()  # rebuilt with the swatches
        self.bindings.on(self.erase_box, "change", self.on_erase_change)
        state.subscribe(lambda _topic: self.render(), DOCUMENT, VIEW, LANGUAGE)
        self.render()

    def on_erase_change(self, _event: Any) -> None:
        self.state.set_erase_tool(bool(self.erase_box.checked))

    def on_swatch(self, index: int, _event: Any) -> None:
        self.state.select_slot(index)

    def render(self) -> None:
        self.swatch_bindings.destroy()
        clear(self.container)
        for index, colour in enumerate(self.state.document.palette):
            active = index == self.state.active_slot and not self.state.erase_tool
            button = create(
                "button",
                class_name="swatch active" if active else "swatch",
                text=str(index + 1),
                attrs={
                    "type": "button",
                    "title": f"{t('colour_slot', number=index + 1)} {colour}",
                    "aria-label": t("colour_slot", number=index + 1),
                    "aria-pressed": "true" if active else "false",
                },
                parent=self.container,
            )
            button.style.setProperty("--swatch", colour)
            self.swatch_bindings.on(button, "click", functools.partial(self.on_swatch, index))
        self.erase_box.checked = self.state.erase_tool


class SymmetryPanel:
    """Checkboxes ``input.sym`` whose ``value`` is a symmetry operation name."""

    def __init__(self, state: AppState) -> None:
        self.state = state
        self.boxes = query_all("input.sym")
        self.bindings = Bindings()
        for box in self.boxes:
            self.bindings.on(box, "change", self.on_change)
        state.subscribe(lambda _topic: self.render(), DOCUMENT)
        self.render()

    def on_change(self, _event: Any) -> None:
        selected = [str(box.value) for box in self.boxes if box.checked]
        self.state.edit(lambda editor: editor.set_symmetry(selected))
        self.render()  # the rules may have refused an operation

    def render(self) -> None:
        doc = self.state.document
        square = doc.unit_width == doc.unit_height
        for box in self.boxes:
            name = str(box.value)
            box.checked = name in doc.symmetry
            box.disabled = name in SQUARE_ONLY_OPERATIONS and not square
