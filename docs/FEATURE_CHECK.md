# Feature check: Tkinter app → web app

Chunk 8, first half. Every behaviour of the Tkinter app (`src/kvale/gui`) and
what the web app (`web/`) does instead.

**The Tkinter app was removed on 2026-10-29** (chunk 8, second half), with its
tests and the `kvale [path.json]` command. The tables below are kept as the
record of what it did. Checked by reading both and by running
the web app (`python tools/build_site.py --serve`) in Chromium with Playwright;
the browser tests named are in `tests/test_web_browser.py` (`pytest -m browser`).

- ✅ same: the web app does it (perhaps with another look).
- ✅ changed on purpose: the web app does it differently, for the reason given.
- ❌ missing: not in the web app.

Fixed in this check (were missing or broken): the thread list in the saved
image, "Undone."/"Redone." messages, shortcuts acting behind open dialogs,
Save as, arrow keys in the thread picker, and a stitch tool chosen in "Whole
band" going back to drawing.

## Files and start-up

| Tkinter | Web | Status |
|---|---|---|
| File → New (Ctrl+N) | "New" button. Asks first when there are unsaved changes | ✅ changed on purpose: browsers keep Ctrl+N for a new window in a normal tab (it works in the installed app); asking first avoids lost work |
| File → Open… (Ctrl+O), `*.json` filter | "Open" and Ctrl+O; the file picker (Chrome, Edge) or a file input, `.json` | ✅ same (`test_open_via_file_input_and_save_round_trip`) |
| Open error: message box "Kunne ikke åpne mønster" | Toast "This file is not a Kvale pattern." or "…made with a newer version…" | ✅ same (`test_open_bad_file_shows_a_message`) |
| File → Save (Ctrl+S); first save asks for a name | "Save" and Ctrl+S: writes back to the opened file (Chrome, Edge) or downloads `<name>.json` | ✅ same |
| File → Save as… | "Save as…" button and Ctrl+Shift+S: asks where to save (Chrome, Edge), later saves go there; other browsers download | ✅ fixed in this check (`test_save_as_asks_for_a_new_file`, `test_save_as_button`). The button was added on the owner's decision |
| Save error: message box | Writing to the file fails → the file is downloaded instead | ✅ changed on purpose: nothing is lost |
| File → Export PNG… (cell 18 px, grid lines, backstitch, end pieces) | "Save image": the whole band with grid, backstitch, ends and corners, **and the thread list under it** ("DMC 321 – Red", "Own colour #123456"); its tooltip says so | ✅ changed on purpose: 16 px per square, smaller for very long bands so the image stays under 8000 px; the thread list is new (design). Fixed in this check (`test_png_lists_the_threads`, `test_render_image_with_key_*`) |
| File → Quit | Close the tab; it warns when changes are not saved to a file | ✅ changed on purpose |
| `kvale path.json` opens a file at start; error box if it fails (the command was removed with the Tkinter app) | `?file=<url>`, `?example=<name>` or `#data=<compressed JSON>`; a toast if it fails | ✅ same (`test_example_from_url`, `test_data_link_and_missing_example`) |
| — | Autosave in the browser, restored on the next visit; unsaved marker | ✅ new (`test_autosave_restores_after_reload`) |

## Status messages

| Tkinter (status bar) | Web | Status |
|---|---|---|
| "Klar" at start | Nothing shown | ✅ changed on purpose: the toast only appears when there is news |
| "Endret" after every change | The ● unsaved marker by the pattern name | ✅ changed on purpose |
| "Angret siste endring" / "Gjorde om siste endring" | Toast "Undone." / "Redone." (with Undo after a redo) | ✅ fixed in this check: before, only the toast's own Undo said so (`test_undo_redo_keys_buttons_and_messages`) |
| "Nytt dokument", "Åpnet X", "Lagret X", "Eksporterte X" | The pattern name and the unsaved marker change; the browser shows the download | ✅ changed on purpose: the name area says it all the time |
| "Kvadratisk enhet kreves" box when square-only symmetry is chosen on a non-square unit | Toast; the square-only tiles are disabled on a non-square unit | ✅ same (`test_square_only_symmetry_is_switched_off_with_a_message`) |
| Resizing to a non-square unit switches square-only symmetry off **quietly** | Switches it off **with** the toast | ✅ changed on purpose: says why the symmetry changed |

## Undo and redo

| Tkinter | Web | Status |
|---|---|---|
| Edit → Undo (Ctrl+Z), Redo (Ctrl+Y, Ctrl+Shift+Z) | Undo/Redo buttons; Ctrl+Z, Ctrl+Y, Ctrl+Shift+Z, and Cmd on a Mac | ✅ same (`test_undo_redo_keys_buttons_and_messages`) |
| Menu entries disabled when there is nothing to undo/redo | Buttons disabled | ✅ same |
| History of 100 steps | 100 steps; a drag stroke is one step | ✅ same (`test_drag_stroke_is_one_undo_step`) |
| Shortcuts do not reach the main window while a dialog is open (grab) | No shortcut runs while a dialog is open; Ctrl+Z there undoes typing | ✅ fixed in this check: Ctrl+Z, P and 1–9 used to change the pattern behind a dialog (`test_shortcuts_wait_while_a_dialog_is_open`) |
| Undo puts the active colour back to slot 1 | Keeps the active colour (moves it only if the slot is gone) | ✅ changed on purpose |

## Grid settings

| Tkinter | Web | Status |
|---|---|---|
| Unit width/height, repeats across/down, 1–100 (spinboxes + "Bruk") | Steppers 1–100, applied at once | ✅ same (`test_size_and_repeats`) |
| Invalid number: "Ugyldige innstillinger" box | The stored value is shown again | ✅ changed on purpose |
| Resize keeps marks from the top-left, drops what falls outside; end-piece extensions move with the edge | The same core call (`Editor.set_grid` → `resize_unit`) | ✅ same |
| Toggles: left/right column, top/bottom row part of the repeat | Switches with a small diagram | ✅ same |
| Grid → Add/remove row or column…: top/bottom row, first/last column, numbered row/column; symmetry adds/removes the matching ones; note about symmetry | The rows and columns dialog, plus the ruler popovers; lists exactly which rows/columns change | ✅ same (`test_rows_and_columns_dialog`, `test_ruler_popover_adds_and_removes_rows`) |
| "Kan ikke fjerne" when it would remove the last row/column | Toast | ✅ same |
| Number spinner capped at the last row/column | Capped | ✅ same |

## Symmetry

| Tkinter | Web | Status |
|---|---|---|
| 8 operations as checkboxes ("Original" always on) | 8 tiles in groups | ✅ same |
| Square-only operations switched off with a message on non-square units | Same, and the tiles are disabled | ✅ same |
| Symmetry checkboxes follow undo and row/column changes | Tiles follow the document | ✅ same (`test_paint_mirror_erase_and_undo`) |

## Drawing

| Tkinter | Web | Status |
|---|---|---|
| Left click paints, right click erases | Same; also drag and touch, and the unpick tool (E) | ✅ same (`test_paint_mirror_erase_and_undo`, `test_eraser_toggle`) |
| Clicking a generated copy edits its source mark | Only the minimal cell can be edited; the rest is greyed out | ✅ changed on purpose (README, "Minimal cell") (`test_click_outside_minimal_cell_does_nothing`) |
| Seed marks: dark inset border; generated marks: none | Same, and generated cells are dimmed | ✅ same |
| Row/column numbers on all four sides | Numbered rulers on top and left, which also open the row/column popover | ✅ changed on purpose (design) |
| Hint "Venstre: farg/legg til, høyre: slett." | Hint under the grid for the chosen tool and target | ✅ same (`test_tool_hint`) |
| Redraws to fit the window on resize | Same, plus zoom (Ctrl +/−/0) | ✅ same |
| "Rediger mønster" / "Se repetisjoner" | "Draw" / "Whole band" (P toggles) | ✅ same (`test_preview_mode`) |
| Choosing a stitch tool switches to edit mode | Same (button or X/B/E) | ✅ fixed in this check: in "Whole band" the tool changed but nothing showed it (`test_choosing_a_tool_in_the_whole_band_goes_back_to_drawing`) |

## Backstitch

| Tkinter | Web | Status |
|---|---|---|
| "Attersting": click two intersections to draw a line | Backstitch tool (B); lines chain from the last point (design) | ✅ changed on purpose (`test_backstitch_chains_and_stops`) |
| Dashed preview line in the active colour, following the mouse | Same (grey when the line is not allowed) | ✅ same |
| Points must be inside the editable area | Same, and in the minimal cell | ✅ same (`test_backstitch_only_in_the_minimal_cell`) |
| Right click removes the nearest line | Same; the unpick tool also removes a line under it | ✅ same (`test_backstitch_chains_and_stops`) |
| Esc cancels the pending line | Esc stops the chain; so do tapping the last point again and choosing another tool | ✅ same |
| Changing mode, tool or target cancels the pending line | Same | ✅ same |
| Expanded by symmetry; drawn in preview and PNG | Same | ✅ same |

## End pieces

| Tkinter | Web | Status |
|---|---|---|
| Edit target: unit, top, bottom, left, right repeat; choosing one switches to edit mode | "Drawing in" bar and mini band; also the four corners (design) | ✅ same (`test_end_piece_edit_extend_reset_and_undo`, `test_corner_edit_and_mini_band`) |
| Right click hides a cell/backstitch, left click adds or recolours | Same | ✅ same |
| Hidden cells: red cross; added cells: inset border; hidden backstitches: red dashed; unit edge lines | Same | ✅ same |
| Extension rows/columns labelled V1/H1/T1/B1 | Labelled +1, +2 … on the rulers | ✅ changed on purpose (design) |
| "Ekstra rader/kolonner utover" 0–100, "Bruk" | Stepper 0–50, applied at once | ✅ changed on purpose: the design caps it at 50, and the owner confirmed that 50 is enough. Files with more still open and draw |
| Controls disabled while the unit is the target | The end panel shows only for an end piece | ✅ same |
| "Nullstill valgt endestykke" asks first | "Reset" asks first and lists what will be lost; undo brings it back | ✅ same |

## Colours

| Tkinter | Web | Status |
|---|---|---|
| Slot list "Farge N"; selected slot outlined and bold | "#N", the thread code ("DMC 321" or "3 colours in turn"), "✓ selected" | ✅ changed on purpose (design: thread codes name their brand) |
| Split legend swatch: a slot's bar is divided into its sequence colours | Same (`.swatchbar`) | ✅ same (`test_colour_sequence_editing`) |
| Click selects; double-click opens the sequence dialog | Same, and a pencil button; keys 1–9 select | ✅ same |
| Selected slot scrolled into view | The slot list is not a separate scroll area | ✅ changed on purpose |
| Sequence dialog: number of colours 1–24, part to edit, numbered preview, OK/Cancel; no change → no undo step | Colour dialog: parts 1–24, preview along the band, Apply/Cancel; no change → no undo step | ✅ same (`test_colour_sequence_editing`) |
| "Bruk fargeskvens" | "Change colour from repeat to repeat" switch | ✅ same |
| "Legg til farge" (RGB dialog, starts grey) and "Legg til DMC-farge…" | One "Add colour", which opens the thread picker with "Own colour …" | ✅ changed on purpose (design decision 4) (`test_add_a_dmc_thread_through_the_picker`) |
| RGB dialog: R/G/B sliders and spinboxes, hex entry (#RGB too), bad-hex message, preview with readable text, "Velg fra DMC-palett…", Esc | Colour dialog: colour wheel, hex or "r, g, b" entry (#RGB too, marked invalid when wrong), quick threads, "Find a thread …", Esc | ✅ changed on purpose: the browser's colour wheel replaces the sliders |
| DMC picker: search by number or name, list (number, name, screen colour), details with RGB, "screen colours are approximate", double-click or "Velg", starts on the current colour, Esc | Thread picker: brand selector, search ("DMC 321" or "321" or a name), colour families, double-click or "Choose", Enter, starts on the current thread, the same note | ✅ same; the RGB numbers are not shown (design) |
| Picker: Down arrow from the search box into the list | Up/Down from the search box move through the list, Enter chooses | ✅ fixed in this check (`test_thread_picker_arrow_keys_and_enter`) |
| — | Background (fabric) colour | ✅ new |
| — | Thread list under the whole band | ✅ new (`test_background_colour_and_thread_list`) |

## Still missing

Nothing from the Tkinter app. The owner decided the three open questions:

- Save as gets a button, "Lagre som …" / "Save as…" / "Salva con nome…", next to Save (it also stays on Ctrl+Shift+S).
- The end-piece extension stepper stopping at 50 is a deliberate change (Tkinter allowed 100). Files with more still open and draw.
- The saved image's tooltip (`file.export.hint`) now says the image includes a list of the threads used.

## Tkinter removed (2026-10-29)

With every behaviour above in the web app, the Tkinter interface was removed:
`src/kvale/gui/`, the `kvale` console command (`src/kvale/__main__.py`, which only
started that interface), and its tests (`test_gui.py`, `test_gui_golden.py`,
`gui_scenarios.py`, `generate_gui_golden.py`, `tests/data/golden/gui.json`).
Opening a file at start is now the Open button or a `?file=` link. `kvale.core`
and its tests, including the golden data of `test_golden.py`, are unchanged.
