"""The "Drawing in" bar, end pieces and corners (chunk 4; a stub for now).

Belongs here:

- ``#target-bar`` (hidden until filled): buttons in ``#target-seg`` for the
  unit and the four ends, and in ``#corner-seg`` for the four corners, named by
  ``state.TARGET_LABEL_KEYS``; a dot (``target.changed``) on changed pieces.
  A click calls ``state.set_edit_target(target)``.
- ``#end-panel``: title, explanation, summary, extra rows/columns stepper
  (``Editor.set_end_piece_extension``), Reset and Done (``end.*``, ``corner.*``).
- ``#reset-dialog``: "Reset this end/corner?" before ``Editor.reset_end_piece``
  (``end.confirm.*``, ``corner.confirm.*``); afterwards
  ``state.set_status("end.resetDone", name=...)``.

Read ``state.edit_target``; re-render on ``VIEW`` (target changed),
``DOCUMENT`` (changed-dots, summary) and ``LANGUAGE``.
"""

from __future__ import annotations

from kvale_web.dom import Element, by_id
from kvale_web.state import AppState


class TargetBar:
    def __init__(self, state: AppState) -> None:
        self.state = state
        self.bar: Element = by_id("target-bar")
        self.end_panel: Element = by_id("end-panel")
        self.reset_dialog: Element = by_id("reset-dialog")
