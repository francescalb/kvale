"""The "Repeat and size" card: ``#grid-card``.

- ``#grid-settings``: unit width/height and repeats across/down, each a
  stepper from 1 to 100 (``Editor.set_grid``), and "Add or remove a
  row/column …", which opens the rows and columns dialog;
- ``#edge-toggles``: whether the outer left/right column and top/bottom row
  are in every repeat or shared by neighbouring repeats, with a small diagram
  of a 3 × 2 band drawn with the current toggles.
"""

from __future__ import annotations

import functools
from typing import Any

from kvale_web.dom import Bindings, by_id, clear, create, query_all
from kvale_web.i18n import t
from kvale_web.panels.grid_model import EDGE_FIELDS, GRID_FIELDS, clamp_setting, edge_diagram
from kvale_web.panels.lines import open_lines_dialog
from kvale_web.state import DOCUMENT, LANGUAGE, AppState

# Diagram cell size and colours (the design's: outer columns blue, outer rows ochre).
_CELL = 12
_FILL = {"column": "#2f5d9e", "row": "#c08a1e", "inner": "var(--surface)"}


class GridSettingsPanel:
    def __init__(self, state: AppState) -> None:
        self.state = state
        self.card = by_id("grid-card")
        self.inputs = {field: by_id(f"grid-{field}") for field in GRID_FIELDS}
        self.edge_list = by_id("edge-list")
        self.edge_bindings = Bindings()

        self.bindings = Bindings()
        for button in query_all("#grid-settings [data-step]"):
            field, step = str(button.dataset.field), int(button.dataset.step)
            self.bindings.on(button, "click", functools.partial(self.on_step, field, step))
        for field, element in self.inputs.items():
            self.bindings.on(element, "change", functools.partial(self.on_input, field))
            self.bindings.on(element, "keydown", functools.partial(self.on_key, field))
        self.bindings.on(by_id("open-lines"), "click", lambda _event: open_lines_dialog())
        state.subscribe(lambda _topic: self.render(), DOCUMENT, LANGUAGE)
        self.render()
        self.card.hidden = False

    # Events ------------------------------------------------------------

    def set_field(self, field: str, value: object) -> None:
        number = clamp_setting(value)
        if number is None or number == getattr(self.state.document, field):
            self.render()  # show the stored value again
            return
        self.state.edit(lambda editor: editor.set_grid(**{field: number}))  # type: ignore[arg-type]
        self.render()

    def on_step(self, field: str, step: int, _event: Any) -> None:
        self.set_field(field, getattr(self.state.document, field) + step)

    def on_input(self, field: str, _event: Any) -> None:
        self.set_field(field, self.inputs[field].value)

    def on_key(self, field: str, event: Any) -> None:
        if event.key == "Enter":
            event.preventDefault()
            self.on_input(field, event)

    def on_edge(self, edge: str, _event: Any) -> None:
        name = EDGE_FIELDS[edge]
        value = not getattr(self.state.document, name)
        self.state.edit(lambda editor: editor.set_grid(**{name: value}))

    # Drawing -----------------------------------------------------------

    def render(self) -> None:
        doc = self.state.document
        for field, element in self.inputs.items():
            element.value = str(getattr(doc, field))

        self.edge_bindings.destroy()
        clear(self.edge_list)
        for edge, name in EDGE_FIELDS.items():
            on = bool(getattr(doc, name))
            row = create("div", class_name="toggle-row", parent=self.edge_list)
            text = create("div", class_name="text", parent=row)
            create("strong", text=t(f"edges.{edge}"), parent=text)
            create("span", text=t("edges.on") if on else t(f"edges.off.{edge}"), parent=text)
            wrap = create("div", class_name="switch-wrap", parent=row)
            switch = create(
                "button",
                class_name="switch",
                attrs={
                    "type": "button",
                    "role": "switch",
                    "data-edge": edge,
                    "aria-checked": "true" if on else "false",
                    "aria-label": t(f"edges.{edge}"),
                },
                parent=wrap,
            )
            self.edge_bindings.on(switch, "click", functools.partial(self.on_edge, edge))

        diagram = edge_diagram(doc)
        parts = []
        for cell in diagram.cells:
            opacity = "" if cell.kind == "inner" else ' fill-opacity=".85"'
            parts.append(
                f'<rect x="{cell.x * _CELL + 0.5}" y="{cell.y * _CELL + 0.5}" width="{_CELL - 1}" '
                f'height="{_CELL - 1}" style="fill:{_FILL[cell.kind]}"{opacity}/>'
            )
        for x, y, w, h in diagram.units:
            parts.append(
                f'<rect x="{x * _CELL}" y="{y * _CELL}" width="{w * _CELL}" height="{h * _CELL}" '
                'fill="none" style="stroke:var(--text)" stroke-width="1.5"/>'
            )
        width, height = diagram.width * _CELL, diagram.height * _CELL
        svg = by_id("edge-diagram")
        svg.setAttribute("viewBox", f"-1 -1 {width + 2} {height + 2}")
        svg.setAttribute("width", str(width + 2))
        svg.setAttribute("height", str(height + 2))
        svg.innerHTML = "".join(parts)
