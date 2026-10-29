"""Legend, mini band and the whole-band caption.

- ``#legend``: what the marks on the grid mean, for the unit, an end or a corner.
- ``#mini-band``: the whole band, small, under the legend. The piece being
  edited is framed; clicking an end or a corner edits it ("Show large" opens
  the whole band). It is redrawn a moment after the last change, so drawing
  stays quick on large bands.
- ``#preview-caption``: "{rx} × {ry} repeats · {w} × {h} stitches".
"""

from __future__ import annotations

from typing import Any

from pyscript import window
from pyscript.ffi import create_proxy

from kvale.core.editing import EditTarget
from kvale_web.dom import Bindings, by_id
from kvale_web.grid import paint
from kvale_web.grid.scene import (
    BandLayout,
    band_layout,
    is_corner,
    path_rects,
    region_at,
    region_rect,
    title_key,
)
from kvale_web.i18n import t
from kvale_web.state import DOCUMENT, LANGUAGE, VIEW, AppState

MINI_CELL = 7
MINI_DELAY_MS = 150

LEGEND_UNIT = (("k-seed", "legend.seed"), ("k-copy", "legend.copy"), ("k-back", "legend.back"))
LEGEND_END = (
    ("k-unit", "legend.fromUnit"),
    ("k-added", "legend.added"),
    ("k-removed", "legend.removed"),
    ("k-extra", "legend.extra"),
    ("k-nb", "legend.neighbour"),
)
LEGEND_CORNER = (
    ("k-unit", "legend.fromEnds"),
    ("k-added", "legend.addedCorner"),
    ("k-removed", "legend.removedCorner"),
    ("k-extra", "legend.extra"),
    ("k-nb", "legend.neighbourEnds"),
)

_MINI_HTML = """
<header>
  <h3 data-i18n="band.mini.title">Slik blir borden</h3>
  <button type="button" class="btn ghost" id="mini-open"><span data-i18n="band.mini.open">Vis stort</span><svg class="icon"><use href="#i-band"/></svg></button>
</header>
<canvas id="mini-canvas"></canvas>
<p class="hint" data-i18n="band.mini.hint">Trykk på en ende eller et hjørne av borden for å gi den sin egen avslutning.</p>
"""


class Overview:
    def __init__(self, state: AppState) -> None:
        self.state = state
        self.legend = by_id("legend")
        self.mini_band = by_id("mini-band")
        self.mini_band.innerHTML = _MINI_HTML
        self.mini_canvas = by_id("mini-canvas")
        self.caption = by_id("preview-caption")
        self.layout: BandLayout | None = None
        self.cell = MINI_CELL
        self.hover: EditTarget | None = None
        self._timer: int | None = None
        self._draw_proxy = create_proxy(self._timed_draw)
        self._legend_key: object = None

        self.bindings = Bindings()
        self.bindings.on(by_id("mini-open"), "click", lambda _event: state.set_mode("preview"))
        self.bindings.on(self.mini_canvas, "pointermove", self.on_mini_move)
        self.bindings.on(self.mini_canvas, "pointerleave", self.on_mini_leave)
        self.bindings.on(self.mini_canvas, "click", self.on_mini_click)
        self.bindings.on(window, "resize", lambda _event: self.schedule())
        state.subscribe(self._on_change, DOCUMENT, VIEW, LANGUAGE)
        self.mini_band.hidden = False
        self.render_legend()

    def _on_change(self, topic: str) -> None:
        self.render_legend()
        if self.state.mode == "preview":
            self.render_caption()
        elif topic == DOCUMENT:
            self.schedule()
        else:
            self.draw_mini()

    # Legend and caption ----------------------------------------------------

    def render_legend(self) -> None:
        target = self.state.edit_target
        items = LEGEND_UNIT if target == "unit" else LEGEND_CORNER if is_corner(target) else LEGEND_END
        key = (items, t(items[0][1]))
        if key == self._legend_key:
            return
        self._legend_key = key
        self.legend.innerHTML = "".join(
            f'<span><i class="key {css}"></i><span>{t(text)}</span></span>' for css, text in items
        )

    def render_caption(self) -> None:
        doc = self.state.document
        layout = band_layout(doc)
        self.caption.textContent = t(
            "preview.caption", rx=doc.repeats_x, ry=doc.repeats_y, w=layout.width, h=layout.height
        )

    # Mini band -------------------------------------------------------------

    def schedule(self) -> None:
        """Redraw the mini band shortly, once the changes stop."""
        if self._timer is not None:
            window.clearTimeout(self._timer)
        self._timer = window.setTimeout(self._draw_proxy, MINI_DELAY_MS)

    def _timed_draw(self) -> None:
        self._timer = None
        if self.state.mode == "edit":
            self.draw_mini()

    def draw_mini(self) -> None:
        if self.state.mode != "edit":
            return
        doc = self.state.document
        layout = band_layout(doc)
        max_width = max(60, int(self.mini_band.clientWidth) - 26)
        cell = max(2, min(MINI_CELL, max_width // max(1, layout.width)))
        cell = paint.clamp_cell(cell, layout.width, layout.height)
        ctx = paint.size_canvas(self.mini_canvas, layout.width * cell, layout.height * cell)
        self.layout = paint.draw_band(ctx, doc, cell, 0, 0)
        self.cell = cell
        target = self.state.edit_target
        width, height = layout.width * cell, layout.height * cell
        x, y, w, h = (value * cell for value in region_rect(layout, target))
        accent = paint.token("--accent", "#9e1b2c")
        if target != "unit":
            paint.fill(
                ctx, path_rects([(0, 0, width, height), (x, y, w, h)]),
                paint.token("--surface", "#ffffff"), alpha=0.55, evenodd=True,
            )
        frame = path_rects([(x + 1.25, y + 1.25, w - 2.5, h - 2.5)])
        paint.stroke(ctx, frame, accent, 2.5, dash=(5, 3) if target == "unit" else ())
        if self.hover is not None and self.hover != target:
            hx, hy, hw, hh = (value * cell for value in region_rect(layout, self.hover))
            paint.stroke(
                ctx, path_rects([(hx + 1, hy + 1, hw - 2, hh - 2)]),
                paint.token("--focus", "#2f5d9e"), 2, dash=(3, 3),
            )

    def _region(self, event: Any) -> EditTarget | None:
        if self.layout is None:
            return None
        rect = self.mini_canvas.getBoundingClientRect()
        scale = float(rect.width) / max(1.0, float(self.layout.width * self.cell)) or 1.0
        cx = int(float(event.clientX - rect.left) / scale // self.cell)
        cy = int(float(event.clientY - rect.top) / scale // self.cell)
        return region_at(self.layout, cx, cy)

    def on_mini_move(self, event: Any) -> None:
        region = self._region(event)
        if region != self.hover:
            self.hover = region
            self.mini_canvas.title = "" if region is None else (
                t("target.unit.hint") if region == "unit" else t(title_key(region))
            )
            self.draw_mini()

    def on_mini_leave(self, _event: Any) -> None:
        if self.hover is not None:
            self.hover = None
            self.draw_mini()

    def on_mini_click(self, event: Any) -> None:
        region = self._region(event)
        if region is not None:
            self.state.set_edit_target(region)
