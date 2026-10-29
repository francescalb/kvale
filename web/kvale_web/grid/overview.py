"""Legend, mini band and the whole-band caption (chunk 4; a stub for now).

Belongs here:

- ``#legend``: keys for the current view (``legend.*``);
- ``#mini-band`` (hidden until filled): the small whole-band view; clicking an
  end or corner calls ``state.set_edit_target(...)`` (``band.mini.*``);
- ``#preview-caption``: "{rx} × {ry} repeats · {w} × {h} stitches"
  (``preview.caption``).

Re-render on ``DOCUMENT``, ``VIEW`` and ``LANGUAGE``.
"""

from __future__ import annotations

from kvale_web.dom import Element, by_id
from kvale_web.state import AppState


class Overview:
    def __init__(self, state: AppState) -> None:
        self.state = state
        self.legend: Element = by_id("legend")
        self.mini_band: Element = by_id("mini-band")
        self.caption: Element = by_id("preview-caption")
