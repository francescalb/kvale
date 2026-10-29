# Kvale modernisation plan

Goal: turn the Tkinter program into an app that non-technical users can open on
Windows, macOS and Linux without a command line, while keeping all existing
features and leaving room for new ones.

## Decisions

| Topic | Decision |
|---|---|
| Where it runs | In the browser, as a static site on GitHub Pages (no server) |
| Language | As much Python as possible. `kvale.core` runs in the browser via Pyodide |
| Interface languages | Norwegian (nb), English (en), Italian (it), switchable in the app |
| UI toolkit | PyScript: Python for all logic, plain HTML/CSS for layout and look, no build step. Chosen over Flet after the toolkit test (faster start, smaller download, faster with large grids, normal web page) |

## Feature checklist

Every item must work in the new app before the Tkinter interface is removed.

- [x] Unit width/height and repeats across/down (1–100)
- [x] Toggles for whether the outer left/right column and top/bottom row repeat
- [ ] Left-click paints, right-click erases; clicking a generated copy edits the source mark (Tkinter only)
- [x] Web: with symmetry on, only the minimal cell (one cell per symmetry orbit, `core.symmetry.minimal_cell`) can be edited; the rest is greyed out and the minimal cell is outlined, with a hint
- [ ] Seed marks have an inset border; generated marks do not
- [x] Row/column dialog: add or remove the top/bottom row, first/last column or a numbered row/column; symmetry adds/removes the matching ones; the last row/column cannot be removed
- [x] 8 symmetry operations; square-only ones are switched off with a message on non-square units
- [ ] Edit mode and repeat-preview mode
- [ ] Backstitch tool: click two intersections to draw, right-click to remove, Esc cancels; expanded by symmetry; drawn in preview and PNG
- [ ] End pieces for the top, bottom, left and right repeats: hide/add/recolour cells and backstitches, extension with extra rows/columns beyond the unit, reset
- [x] Colour slots: select, edit, add; per-slot sequences (1–24 colours); "use sequence" toggle; split legend swatch
- [x] Colour dialog with RGB/hex entry, and a searchable DMC floss colour picker
- [x] Open/save JSON in the current format (format_version 4; older files still open); PNG export
- [x] Open a pattern given at start (`kvale path.json` today; in the browser `?file=<url>`, `?example=<name>` or `#data=<compressed JSON>`)
- [x] Ctrl+O / Ctrl+S, and a New button (browsers reserve Ctrl+N in a normal tab; it works in the installed app)
- [ ] Undo/redo (Ctrl+Z / Ctrl+Y / Ctrl+Shift+Z), Edit menu entries disabled when there is nothing to undo/redo
- [x] New: control for the background colour (already stored in the file)

Added by the approved design (`docs/design/strings.md`, "Owner-approved design decisions"):

- [ ] Corners: the four corners where two end pieces meet are edited on their own (in the "Drawing in" bar and the mini band), with a dot when changed; applied after the end pieces
- [x] Thread brand + code: a colour is a (brand, code) pair or an own colour, always shown as «DMC 321»; the picker has a brand selector (DMC now, Anchor and Madeira "coming later")
- [ ] Confirm reset: resetting an end piece or a corner asks first and lists what will be lost; undo can still bring it back
- [ ] Backstitch chaining: the next line starts where the last one ended, until Esc, a tap on the last point, or another tool
- [x] Thread list under the whole band (and in the saved image: chunk 6 reuses `thread_rows`)
- [x] Web: light/dark theme, nb/en/it switch, layout of the design (chunk 3)
- [x] Web: autosave in the browser, restored on the next visit; the file name with an unsaved-changes marker; a warning before leaving with unsaved changes (chunk 6)

## Chunks

Each chunk is one pull request.

| # | Chunk | Needs |
|---|---|---|
| 0 | ✅ Toolkit test: throwaway Flet and PyScript apps (branches `spike/flet`, `spike/pyscript`). PyScript chosen | – |
| 1 | ✅ Strengthen the core: move row/column insert/remove, palette-sequence handling and symmetry rules from `gui/app.py` into `core/` with tests; add a single command layer with undo/redo; cleanup | – |
| 2 | PyScript project skeleton (starting from the `spike/pyscript` prototype); GitHub Actions run tests and publish to GitHub Pages | 0 |
| 3 | ✅ Look and languages: layout, light/dark, all UI text in nb/en/it files, language switch; a shared shell with one module, style sheet and set of containers per chunk 4–6 (see `web/README.md`) | 2 |
| 4 | Drawing grid: paint/erase (click, drag, touch), seed vs generated marking, row/column insert/remove, zoom | 1, 3 |
| 5 | ✅ Side panels: grid settings, symmetry, colour slots, sequence editor | 1, 3 |
| 6 | Files: open/save JSON, PNG export, autosave in the browser | 1, 2 |
| 7 | Installable/offline (PWA) and a short user guide in nb/en/it | 4–6 |
| 8 | Feature check against the checklist; remove the Tkinter interface | 7 |

Rounds: 0+1, then 2+3, then 4+5+6, then 7+8. Pull requests are reviewed after
each round before the next one starts.

## Later

Printable charts with a symbol per colour (SVG/PDF), named thread palettes,
half-drop and brick repeats, draggable mirror lines, and the roadmap in the README.
