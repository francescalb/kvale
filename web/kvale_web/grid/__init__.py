"""The stage (chunk 4): drawing grid, tools, zoom, rulers, end pieces and corners.

``app.py`` calls ``mount(state)`` once. Add new views to ``GridViews`` here,
so ``app.py`` and the other chunks never need to change.

Modules: ``canvas`` (the grid canvas), ``tools`` (stitch tools and hint),
``target`` ("Drawing in" bar, end panel, reset confirm), ``zoom``,
``rulers`` (rulers and the row/column popover) and ``overview`` (legend,
mini band, preview caption).
"""

from __future__ import annotations

from kvale_web.dom import by_id
from kvale_web.grid.canvas import GridView
from kvale_web.grid.overview import Overview
from kvale_web.grid.rulers import Rulers
from kvale_web.grid.target import TargetBar
from kvale_web.grid.tools import ToolPicker
from kvale_web.grid.zoom import ZoomControls
from kvale_web.state import AppState


class GridViews:
    """Every chunk 4 view, kept alive as long as the page."""

    def __init__(self, state: AppState) -> None:
        self.tools = ToolPicker(state)
        self.target = TargetBar(state)
        self.zoom = ZoomControls(state)
        self.rulers = Rulers(state)
        self.overview = Overview(state)
        self.grid = GridView(state, by_id("grid"))

    def start(self) -> None:
        """First render, once the page and the other views are ready."""
        self.grid.render()


def mount(state: AppState) -> GridViews:
    return GridViews(state)
