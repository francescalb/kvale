"""The stage (chunk 4): drawing grid, tools, zoom, rulers, end pieces and corners.

``app.py`` calls ``mount(state)`` once. Add new views to ``GridViews``, so
``app.py`` and the other chunks never need to change.

Modules: ``scene`` (what the grid shows, as plain data; no ``js``, so it is
tested in CPython), ``paint`` (batched canvas drawing), ``canvas`` (the grid
canvas: edit view, whole band, pointer input, backstitch), ``tools`` (stitch
tools and hint), ``target`` ("Drawing in" bar, end panel, reset confirm),
``zoom``, ``rulers`` (rulers and the row/column popover) and ``overview``
(legend, mini band, whole-band caption).

The browser-only views are imported inside ``mount`` so that importing
``kvale_web.grid.scene`` works without a browser.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
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
        from kvale_web import i18n
        from kvale_web.dom import by_id
        from kvale_web.grid.canvas import GridView
        from kvale_web.grid.overview import Overview
        from kvale_web.grid.rulers import Rulers
        from kvale_web.grid.target import TargetBar
        from kvale_web.grid.tools import ToolPicker
        from kvale_web.grid.zoom import ZoomControls

        self.tools: ToolPicker = ToolPicker(state)
        self.target: TargetBar = TargetBar(state)
        self.zoom: ZoomControls = ZoomControls(state)
        self.rulers: Rulers = Rulers(state)
        self.overview: Overview = Overview(state)
        self.grid: GridView = GridView(state, by_id("grid"), self.zoom, self.rulers)
        # Translate the data-i18n parts of the HTML these views just built.
        i18n.apply_translations()

    def start(self) -> None:
        """First render, once the page and the other views are ready."""
        self.grid.render()
        self.overview.draw_mini()


def mount(state: AppState) -> GridViews:
    return GridViews(state)
