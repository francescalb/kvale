# Kvale

[![CI](https://github.com/francescalb/kvale/actions/workflows/ci.yml/badge.svg)](https://github.com/francescalb/kvale/actions/workflows/ci.yml)
[![PR Validate](https://github.com/francescalb/kvale/actions/workflows/pr-validate.yml/badge.svg)](https://github.com/francescalb/kvale/actions/workflows/pr-validate.yml)

`Kvale` is a modular Python desktop application for designing repeating,
grid-based textile and embroidery patterns. Geometry, symmetry and colouring are
kept separate so that colour sequencing can evolve independently of the geometric repeat.

The first version uses Tkinter for the GUI, Pillow for PNG export, JSON for editable
project files, and a small dependency-free core that can later be reused by a web UI,
CLI, SVG exporter or embroidery-format plugin.

## Features

- Click-to-paint editor for a recurring grid unit
- Live expansion by mirror planes and rotations
- Repeated-band preview
- Per-slot palette sequences edited from the colour dialog
- Toggle to apply sequence over repeats (`Bruk fargeskvens`)
- Undo/redo (Ctrl+Z, Ctrl+Y or Ctrl+Shift+Z)
- JSON save/load
- PNG export
- Unit tests and GitHub Actions
- `src/` package layout suitable for publishing

## Project architecture

```text
src/kvale/
├── core/
│   ├── model.py          # document data model
│   ├── symmetry.py       # symmetry operations and rules
│   ├── editing.py        # edit operations (paint, rows/columns, resize, colours)
│   ├── editor.py         # Editor: command layer with undo/redo
│   ├── renderer.py       # repeat-aware colour grid and raster export
│   └── serialization.py  # JSON persistence
└── gui/
    ├── app.py            # menus, controls and document lifecycle
    └── canvas.py         # interactive editor and preview canvas
```

The GUI depends on interfaces from `core`, but `core` does not depend on the GUI.
That boundary is the main extension point.

A UI holds one `Editor`, calls its methods for every change (`paint`, `erase`,
`insert_column`, `set_grid`, `set_symmetry`, `set_colour_sequence`, ...) and draws
`editor.document`. The editor keeps undo/redo history; wrap a drag-paint stroke in
`with editor.batch():` to make it one undo step. Edits that switch off square-only
symmetry return the removed operations in `EditResult.removed_symmetry`.

## Run locally

Python 3.11 or newer is recommended.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e .[dev]
kvale
```

On Linux, Tkinter may need to be installed through the operating system package
manager, for example `sudo apt install python3-tk` on Ubuntu or Debian.
You might need to specify python version when installing Tkinter: `sudo apt install python3.14-tk`

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
9. Save the editable pattern as JSON or export a PNG.

The legend rectangle for each `#n` slot is subdivided to visualize its current sequence.

## Palette sequence behavior

- Each colour slot (`#1`, `#2`, ...) has its own list of colours.
- If a sequence has one entry, that colour stays constant even when sequencing is enabled.
- If a sequence is shorter than the number of repeats, it restarts from the beginning.

## JSON format

Pattern files now use `palette_sequences` as canonical colour storage.

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

## Tests

```bash
pytest
ruff check .
mypy src tests
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
