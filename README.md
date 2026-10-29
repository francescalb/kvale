# Kvale

[![CI](https://github.com/francescalb/kvale/actions/workflows/ci.yml/badge.svg)](https://github.com/francescalb/kvale/actions/workflows/ci.yml)
[![PR Validate](https://github.com/francescalb/kvale/actions/workflows/pr-validate.yml/badge.svg)](https://github.com/francescalb/kvale/actions/workflows/pr-validate.yml)

`Kvale` is a modular Python application for designing repeating,
grid-based textile and embroidery patterns. Geometry, symmetry and colouring are
kept separate so that colour sequencing can evolve independently of the geometric repeat.

The first version uses Tkinter for the GUI, Pillow for PNG export, JSON for editable
project files, and a small dependency-free core that can later be reused by a web UI,
CLI, SVG exporter or embroidery-format plugin.

## Features

- Click-to-paint editor for a recurring grid unit
- Live expansion by mirror planes and rotations
- Repeated-band preview
- Backstitch (`Attersting`): a second tool that draws lines between grid
  intersections, expanded by the same symmetry as the cross stitches
- End pieces (`Endestykker`): the top, bottom, left and right repeats can each
  hide cells and backstitches of the unit, add their own, and extend beyond the
  unit with extra rows or columns
- Corner end pieces (core only so far): each of the four corner units can be
  changed on its own, including the square where two extensions cross
- Dialog for adding or removing a row or column (`Rutenett` menu); the active
  symmetry adds or removes the matching rows/columns too
- Per-slot palette sequences edited from the colour dialog
- Toggle to apply sequence over repeats (`Bruk fargeskvens`)
- Colours from an RGB/hex dialog or a searchable DMC floss colour picker
- Undo/redo (Ctrl+Z, Ctrl+Y or Ctrl+Shift+Z)
- JSON save/load; `kvale path/to/pattern.json` opens a file at start
- PNG export (including backstitches and end pieces)
- Unit tests and GitHub Actions
- `src/` package layout suitable for publishing

## Project architecture

```text
src/kvale/
├── __main__.py           # `kvale [path]` entry point
├── core/
│   ├── model.py          # document data model (marks, backstitches, end pieces)
│   ├── symmetry.py       # symmetry operations and rules
│   ├── editing.py        # edit operations (paint, backstitch, end pieces,
│   │                     #   rows/columns, resize, colours)
│   ├── editor.py         # Editor: command layer with undo/redo
│   ├── renderer.py       # repeat-aware colour grid, backstitch segments, PNG export
│   ├── serialization.py  # JSON persistence
│   ├── dmc.py            # DMC floss colours (data in dmc_palette.json)
│   └── dmc_palette.json
└── gui/                  # Tkinter interface (removed in chunk 8)
    ├── app.py            # menus, controls, dialogs and document lifecycle
    ├── canvas.py         # interactive editor and preview canvas
    ├── palette_button.py # colour slot buttons and the RGB/hex colour dialog
    └── dmc_palette.py    # DMC colour picker dialog

web/                      # browser app (PyScript), published to GitHub Pages
├── index.html            # static markup and the loading screen
├── style.css             # styles; colours and spacing are tokens at the top
├── pyscript.toml         # PyScript config ([files] is added by the build)
├── main.py               # entry point: runs kvale_web.app.start()
├── i18n/{nb,en,it}.json  # interface strings
└── kvale_web/            # UI package: app, state, i18n, dom, shortcuts,
                          # toolbar, canvas, panels, files
tools/build_site.py       # builds _site/ from web/ and kvale.core
```

The GUI depends on interfaces from `core`, but `core` does not depend on the GUI.
That boundary is the main extension point. `core` is pure Python; Pillow is only
imported when `render_image` is called, so `import kvale.core` works without it.

A UI holds one `Editor`, calls its methods for every change and draws
`editor.document`:

- cells: `paint(x, y, slot, target)`, `erase(x, y, target)`, where `target` is
  `"unit"`, one of the edge end pieces `"top"`, `"bottom"`, `"left"`, `"right"`
  or one of the corners `"top_left"`, `"top_right"`, `"bottom_left"`,
  `"bottom_right"`;
- backstitches: `add_backstitch(start, end, slot, target)`,
  `erase_backstitch_near(x, y, target)`;
- end pieces: `set_end_piece_extension(edge, n)` (edges only),
  `reset_end_piece(edge_or_corner)`;
- grid: `change_grid_line(axis, index, insertion=...)` (and `insert_column`,
  `remove_row`, ...), `set_grid(...)`, `set_symmetry(...)`;
- colours: `add_colour`, `set_colour_sequence`, `set_use_palette_sequence`,
  `set_background`.

`kvale.core.editing` has the helpers a UI needs to draw and validate input, such
as `editor_bounds`, `visible_backstitches`, `hidden_backstitches`,
`can_remove_grid_line`, `grid_line_for_place` and `max_line_number`. The editor
keeps undo/redo history; wrap a drag-paint stroke in `with editor.batch():` to
make it one undo step. Edits that switch off square-only symmetry return the
removed operations in `EditResult.removed_symmetry`.

## Run locally

Python 3.11 or newer is recommended.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e .[dev]
kvale                            # or: kvale examples/flower-band.json
```

On Linux, Tkinter may need to be installed through the operating system package
manager, for example `sudo apt install python3-tk` on Ubuntu or Debian.
You might need to specify python version when installing Tkinter: `sudo apt install python3.14-tk`

## Run the web app locally

The new browser version runs Python in the page with
[PyScript](https://pyscript.net). No Node or npm is needed:

```bash
python tools/build_site.py --serve
```

Then open <http://localhost:8000/>. The command copies `web/` and `src/kvale/core`
into `_site/` and serves it (`--serve 8765` picks another port). Start-up takes a
few seconds while Python loads. The Tkinter app above still works and stays until
the web app has every feature (chunk 8 of the modernisation plan).

### Publishing

`.github/workflows/pages.yml` builds `_site/` and deploys it to GitHub Pages on
every push to `main`. One-time setup in the repository: **Settings → Pages →
Build and deployment → Source: GitHub Actions**. The site is then at
`https://<owner>.github.io/kvale/`; all paths are relative, so the sub-path works.

## Using the editor

1. Set the recurring unit width and height.
2. Select a palette colour.
3. Left-click cells to paint seed marks; right-click to erase.
4. Enable mirrors or rotations. Seed cells have a dark inset border; generated cells do not.
5. Switch to **Preview repeats** to see the complete band.
6. Double-click a colour swatch in **Farger** to open **Velg palettfarge**.
7. In the dialog:
    - Set `Antall farger` (default 1)
    - Select which `Del i sekvens` to edit
    - Use `Velg farge for del` to change that part
8. In **Farger**, toggle `Bruk fargeskvens`:
    - `Av`: only the first colour in each sequence is used for all repeats
    - `På`: sequence advances along repeats and wraps when it reaches the end
9. Choose **Attersting** in the toolbar to draw backstitches: click two grid
   intersections to make a line (Esc cancels); right-click a line to remove it.
   Choose **Korssting** to go back to cross stitches.
10. Under **Endestykker**, pick the top, bottom, left or right repeat to edit how
    that edge of the band differs from the unit: right-click hides a cell or
    backstitch, left-click adds or recolours one. `Ekstra rader/kolonner utover`
    adds rows or columns beyond the unit on that side. `Nullstill valgt
    endestykke` removes all changes for that edge.
11. Use **Rutenett → Legg til/fjern rad eller kolonne...** (or the button under
    **Rutenett**) to add or remove the top/bottom row, the first/last column or a
    numbered row/column. With symmetry on, the matching rows/columns change too.
12. `Legg til farge` picks any colour; `Legg til DMC-farge…` searches DMC floss
    colours by number or name.
13. Save the editable pattern as JSON or export a PNG.

The legend rectangle for each `#n` slot is subdivided to visualize its current sequence.

## Palette sequence behavior

- Each colour slot (`#1`, `#2`, ...) has its own list of colours.
- If a sequence has one entry, that colour stays constant even when sequencing is enabled.
- If a sequence is shorter than the number of repeats, it restarts from the beginning.

## JSON format

Files are written with `"format_version": 4`, or 5 when they have a corner
end piece. Versions up to 5 open, including older files without
`format_version`, backstitches or end pieces.

Pattern files use `palette_sequences` as canonical colour storage.

```json
{
  "palette_sequences": [
     ["#e83608"],
     ["#2d7d32"],
     ["#f2c84b", "#f28ec8"]
  ],
  "use_palette_sequence": true
}
```

- The first colour in each inner list is used as the base colour for that slot.
- `palette` is not written to JSON.
- `backstitches` lists lines between grid intersections:
  `{"start_x": 0, "start_y": 1, "end_x": 2, "end_y": 1, "colour_slot": 0}`.
- `top_repeat_override`, `bottom_repeat_override`, `left_repeat_override` and
  `right_repeat_override` are the end pieces (`null` when unused), each with
  `removed_cells`, `added_marks`, `removed_backstitches`, `added_backstitches`
  and `extension`. Added marks and backstitches may lie in the extension:
  negative coordinates for top/left, at or beyond the unit size for bottom/right.
- `top_left_repeat_override`, `top_right_repeat_override`,
  `bottom_left_repeat_override` and `bottom_right_repeat_override` are the
  corner end pieces, written only when set (format_version 5). They have the
  same fields, but `extension` is always 0: a corner covers the unit, the
  extensions of its two edges and the square where they cross, and is applied
  to the corner unit after the edge end pieces. When an edge's extension
  shrinks (or the edge is reset), corner content outside the new area is dropped.

## Tests

```bash
pytest
ruff check .
mypy src tests web/kvale_web tools
```

Browser smoke tests drive the web app in headless Chromium. They need network
access (PyScript loads from a CDN) and are left out of the default run:

```bash
pip install -e .[dev,browser]
python -m playwright install chromium
pytest -m browser
```

## Pre-commit

```bash
pre-commit install
pre-commit run --all-files
```


## Suggested roadmap

1. Multiple motif layers and named palettes
2. Half-drop, brick and glide-reflection repeats
3. Visual draggable mirror planes
4. SVG and printable chart export
5. Plugin interface for exporters and symmetry groups
6. Optional PySide6 or browser front end
7. Raster-image tracing and palette reduction

## Extension strategy

New functionality should normally be added behind a small interface:

- New edit operation: add a function to `core/editing.py` and a method on `Editor`
  in `core/editor.py`, so every UI gets it with undo/redo.
- New symmetry: add a transform in `core/symmetry.py`.
- New colour behaviour: extend sequence handling in `core/renderer.py` and document model fields in `core/model.py`.
- New export format: consume `PatternDocument` or `build_colour_grid()` in a new exporter module.
- New GUI: reuse the entire `core` package, driving it through `Editor`, without importing Tkinter.

## Licence

BSD-3.0
