"""The Symmetry card: ``#symmetry-options``.

Eight tiles with pictures (``sym.*``): "As you stitch it" is always on; the
mirrors and the half turn work on any repeat; the quarter turns and the
diagonal mirrors need a square repeat. On a repeat that is not square those
are switched off (``normalise_symmetry``), shown as "Needs a square", and a
notice offers "Make the repeat n × n". When a size change switches them off,
``AppState.edit`` shows ``symmetry.switchedOff`` in the toast.
"""

from __future__ import annotations

import functools
from typing import Any

from kvale.core.symmetry import SQUARE_ONLY_OPERATIONS
from kvale_web.dom import Bindings, by_id, clear, create
from kvale_web.i18n import t
from kvale_web.panels.grid_model import SYMMETRY_GROUPS, square_size, symmetry_icon, toggled_symmetry
from kvale_web.state import DOCUMENT, LANGUAGE, AppState

_TICK = '<span class="tick"><svg class="icon"><use href="#i-check"/></svg></span>'


class SymmetryPanel:
    def __init__(self, state: AppState) -> None:
        self.state = state
        self.groups = (by_id("symmetry-any"), by_id("symmetry-square"))
        self.notice = by_id("square-notice")
        self.make_square = by_id("make-square")
        self.tile_bindings = Bindings()
        self.bindings = Bindings()
        self.bindings.on(self.make_square, "click", self.on_make_square)
        state.subscribe(lambda _topic: self.render(), DOCUMENT, LANGUAGE)
        self.render()

    def on_tile(self, operation: str, _event: Any) -> None:
        selected = toggled_symmetry(self.state.document.symmetry, operation)
        self.state.edit(lambda editor: editor.set_symmetry(selected))

    def on_make_square(self, _event: Any) -> None:
        size = square_size(self.state.document)
        self.state.edit(lambda editor: editor.set_grid(unit_width=size, unit_height=size))

    def render(self) -> None:
        doc = self.state.document
        square = doc.unit_width == doc.unit_height
        self.tile_bindings.destroy()
        for container, operations in zip(self.groups, SYMMETRY_GROUPS, strict=True):
            clear(container)
            for operation in operations:
                locked = operation == "identity"
                disabled = operation in SQUARE_ONLY_OPERATIONS and not square
                tile = create(
                    "button",
                    class_name="sym locked" if locked else "sym",
                    attrs={
                        "type": "button",
                        "data-op": operation,
                        "aria-pressed": "true" if operation in doc.symmetry else "false",
                    },
                    parent=container,
                )
                tile.disabled = disabled
                if locked:
                    tile.setAttribute("aria-disabled", "true")
                note = t("symmetry.alwaysOn") if locked else t("symmetry.needsSquare") if disabled else ""
                label = create("span", class_name="lbl")
                create("span", text=t("sym." + operation), parent=label)
                if note:
                    create("small", text=note, parent=label)
                tile.innerHTML = symmetry_icon(operation) + label.outerHTML + _TICK
                if not locked:
                    self.tile_bindings.on(tile, "click", functools.partial(self.on_tile, operation))

        self.notice.hidden = square
        if not square:
            size = square_size(doc)
            by_id("square-notice-text").textContent = t(
                "symmetry.squareNotice", w=doc.unit_width, h=doc.unit_height
            )
            self.make_square.textContent = t("symmetry.makeSquare", n=size)
