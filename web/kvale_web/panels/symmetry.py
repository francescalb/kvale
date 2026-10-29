"""The Symmetry card (chunk 5).

Belongs here: the symmetry buttons with pictures (``sym.*``), the always-on
"As you stitch it", the square-only group with its notice and "Make the
repeat n × n" button (``symmetry.*``), all inside ``#symmetry-options``.

For now: ``SymmetryPanel`` binds the plain checkboxes ``input.sym`` (their
``value`` is a symmetry operation name) that ``index.html`` already has.
"""

from __future__ import annotations

from typing import Any

from kvale.core.symmetry import SQUARE_ONLY_OPERATIONS
from kvale_web.dom import Bindings, query_all
from kvale_web.state import DOCUMENT, AppState


class SymmetryPanel:
    def __init__(self, state: AppState) -> None:
        self.state = state
        self.boxes = query_all("#symmetry-options input.sym")
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
