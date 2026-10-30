# Kvale

[![CI](https://github.com/francescalb/kvale/actions/workflows/ci.yml/badge.svg)](https://github.com/francescalb/kvale/actions/workflows/ci.yml)
[![PR Validate](https://github.com/francescalb/kvale/actions/workflows/pr-validate.yml/badge.svg)](https://github.com/francescalb/kvale/actions/workflows/pr-validate.yml)

`Kvale` is an app for designing repeating, grid-based cross-stitch bands, such as
those on Norwegian bunads. It runs in the browser: the pattern core is pure Python
(`kvale.core`), run in the page by [PyScript](https://pyscript.net), with plain
HTML and CSS for the interface. Geometry, symmetry and colouring are kept separate
so that colour sequencing can evolve independently of the geometric repeat.
Patterns are saved as JSON files and exported as PNG images.

## Use it

Open **<https://francescalb.github.io/kvale/>** in a browser – nothing to download.
The first start takes a few seconds; after one visit the app also works offline.

To install it as an app: in Chrome or Edge press **Install app** in the top bar
(or the install icon in the address bar); on iPhone or iPad tap Share →
**Add to Home Screen**. When a new version is out, the app offers to reload.

The **?** button in the app opens the user guide:
[English](https://francescalb.github.io/kvale/guide/en.html) ·
[norsk](https://francescalb.github.io/kvale/guide/nb.html) ·
[italiano](https://francescalb.github.io/kvale/guide/it.html).

Open a pattern file with **Open** (Ctrl+O), or with a link:
`?file=<url of a .json file>`, `?example=<name>` for one of the patterns in
`examples/` (for example `?example=flower-band`), or `#data=<compressed JSON>`.

Kvale used to be a Tkinter desktop program started with `kvale [path.json]`.
That program and its `kvale` command were removed in October 2026; the web app
does everything it did (see `docs/FEATURE_CHECK.md`).

## Features
- Click, drag or touch to stitch in a recurring grid unit; zoom
- Live expansion by mirror planes and rotations
- Minimal cell: with symmetry on, you draw only in the smallest part of the unit
  that the symmetry copies onto the rest (for example the top-left quarter for
  two mirrors, a triangle for a diagonal). The rest is greyed out, and the
  minimal cell is outlined.
- "Draw" and "Whole band" views
- Backstitch: a second tool that draws lines between grid intersections,
  expanded by the same symmetry as the cross stitches
- End pieces: the top, bottom, left and right repeats can each hide cells and
  backstitches of the unit, add their own, and extend beyond the unit with extra
  rows or columns (up to 50)
- Corners: each of the four corner units can be changed on its own, including
  the square where two extensions cross
- Adding or removing rows and columns (the rulers or the "Rows and columns"
  dialog); the active symmetry adds or removes the matching rows/columns too
- Colours as threads («DMC 321») or own colours, with a searchable DMC picker;
  a colour can change from repeat to repeat (a sequence of up to 24 colours)
- Background (fabric) colour, and the list of threads under the band
- Undo/redo (Ctrl+Z, Ctrl+Y or Ctrl+Shift+Z)
- Open, Save and Save as (JSON), Save image (PNG with the list of threads)
- Autosave in the browser; works offline and can be installed as an app
- Interface in Norwegian, English and Italian; light and dark look

## Project architecture

```text
src/kvale/
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

web/                      # browser app (PyScript), published to GitHub Pages
├── index.html            # static markup and the loading screen
├── style.css             # styles; colours and spacing are tokens at the top
├── pyscript.toml         # PyScript config ([files] is added by the build)
├── main.py               # entry point: runs kvale_web.app.start()
├── i18n/{nb,en,it}.json  # interface strings
├── pwa.js, sw.js         # install button, update toast, offline service worker
├── guide/                # user guide in nb, en and it, with screenshots
├── icons/                # app icons (tools/make_icons.py)
└── kvale_web/            # UI package: app, state, i18n, dom, shortcuts,
                          # toolbar, canvas, panels, files
tools/build_site.py       # builds _site/ from web/ and kvale.core
```

The web app depends on interfaces from `core`, but `core` does not depend on the
web app. That boundary is the main extension point. `core` is pure Python; Pillow is only
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
`can_remove_grid_line`, `grid_line_for_place` and `max_line_number`.
`kvale.core.symmetry.minimal_cell(width, height, operations)` returns the
editable cells under a symmetry (one per orbit), and
`backstitch_in_minimal_cell(start, end, cells)` tells whether a backstitch may
be drawn there. A UI restricts input with them; the stored data is unchanged,
so marks outside the minimal cell (from older files) still render. The editor
keeps undo/redo history; wrap a drag-paint stroke in `with editor.batch():` to
make it one undo step. Edits that switch off square-only symmetry return the
removed operations in `EditResult.removed_symmetry`.

## Run locally
The app needs no installation: use it at <https://francescalb.github.io/kvale/>.
To work on it, use Python 3.11 or newer. No Node or npm is needed:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e .[dev]
python tools/build_site.py --serve
```

Then open <http://localhost:8000/> (or <http://localhost:8000/?example=flower-band>).
The command copies `web/` and `src/kvale/core` into `_site/` and serves it
(`--serve 8765` picks another port). Start-up takes a few seconds while Python
loads. `web/README.md` explains how the web app is organised.

### Publishing

`.github/workflows/pages.yml` builds `_site/` and deploys it to GitHub Pages on
every push to `main`. One-time setup in the repository: **Settings → Pages →
Build and deployment → Source: GitHub Actions**. The site is then at
`https://<owner>.github.io/kvale/`; all paths are relative, so the sub-path works.

## Using the editor
The user guide (the **?** button) explains every step. In short:

1. Under **Repeat and size**, set the size of the repeat and how many repeats go across and down.
2. Choose a colour on the left (or press 1–9).
3. Click or drag on squares to stitch; right-click, or the unpick tool (E), removes them.
4. Turn on mirrors or rotations under **Symmetry**: you draw in the outlined part and
   the rest follows. Stitches you drew have a dark inset border; copies do not.
5. **Whole band** (P) shows the finished band and the threads it uses.
6. The pencil on a colour opens it: choose a thread or an own colour, or several
   that take turns along the band (**Change colour from repeat to repeat**).
7. **Backstitch** (B): tap two grid corners to stitch a line; the next line starts
   where the last ended, until Esc.
8. **Drawing in** picks the repeat, an end piece or a corner. An end piece can hide,
   add or recolour stitches and have extra rows or columns; **Reset** asks first.
9. Click a ruler number, or use **Rows and columns**, to add or remove a row or column.
10. **Save** keeps the pattern as a JSON file, **Save as…** saves a copy under a new
    name, and **Save image** makes a PNG of the whole band with the list of threads.

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
python tools/build_site.py --serve   # then try the app in a browser
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
6. Raster-image tracing and palette reduction

## Extension strategy

New functionality should normally be added behind a small interface:

- New edit operation: add a function to `core/editing.py` and a method on `Editor`
  in `core/editor.py`, so every UI gets it with undo/redo.
- New symmetry: add a transform in `core/symmetry.py`.
- New colour behaviour: extend sequence handling in `core/renderer.py` and document model fields in `core/model.py`.
- New export format: consume `PatternDocument` or `build_colour_grid()` in a new exporter module.
- New interface: reuse the entire `core` package, driving it through `Editor`, as
  `web/kvale_web` does.

## Licence

BSD-3.0
