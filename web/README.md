# Kvale web app: who owns what

The browser app is `index.html` plus the Python package `kvale_web`, run by
PyScript. Build and serve it with `python tools/build_site.py --serve`.
The design is `docs/design/mockup.html`; every UI string is in
`docs/design/strings.md` and already in `i18n/{nb,en,it}.json`.

Chunks 4, 5 and 6 work in parallel. Each owns its own files and its own
containers in `index.html` (marked with an HTML comment naming the owner), so
they should rarely touch the same file.

## Ownership

| | Chunk 4: grid and tools | Chunk 5: side panels | Chunk 6: files |
|---|---|---|---|
| Python | `kvale_web/grid/` (`canvas`, `tools`, `target`, `zoom`, `rulers`, `overview`) | `kvale_web/panels/` (`colours`, `symmetry`, `grid_settings`, `colour_dialog`, `thread_picker`, `lines`, `thread_key`) | `kvale_web/files/` (`logic`, `browser`, `views`) |
| CSS | `grid.css` | `panels.css` | `files.css` |
| Containers | `#tool-seg`, `#zoom-controls`, `#target-bar` (`#target-seg`, `#corner-seg`), `#end-panel`, `#editor` (`#ruler-top`, `#ruler-left`, `#grid`, `#edge-popover`), `#legend`, `#canvas-hint`, `#minimal-cell-hint`, `#mini-band`, `#preview-caption`, `<dialog id="reset-dialog">` | `#colours-card` (`#colour-slots`, `#colour-actions`, `#colour-sequence-toggle`, `#background-row`), `#symmetry-card` (`#symmetry-options`), `#grid-card` (`#grid-settings`, `#edge-toggles`), `#thread-key`, `<dialog>`s `#colour-dialog`, `#thread-dialog`, `#lines-dialog` | `#file-actions`, `#doc-info`, `#boot-restore` |
| Strings | `tool.*`, `zoom.*`, `target.*`, `end.*`, `corner.*`, `legend.*`, `canvas.*`, `band.*`, `preview.*`, `edge.*`, `grid.colN`/`rowN`/`newColN`/`newRowN`, `list.and` | `panel.*`, `colours.*`, `symmetry.*`, `sym.*`, `grid.*`, `edges.*`, `step.*`, `dialog.*`, `thread.*`, `threads.*`, `lines.*` | `file.*`, `autosave.*`, `loading.restore` |
| Mounted by | `grid.mount(state)` | `panels.mount(state)` | `files.mount(state)`, then `await files.start()` |

Shared (chunk 3, change only with care and say so in the PR): `index.html`
outside the owned containers, `style.css`, `tokens.css` (a copy of
`docs/design/tokens.css`), `kvale_web/app.py`, `state.py`, `shell.py`
(language, theme, Draw / Whole band, undo/redo, toast), `i18n.py`, `dom.py`,
`shortcuts.py` and `i18n/*.json`.

To add a view, construct it in your own package's `mount` class
(`GridViews`, `PanelViews`, `FileViews`); `app.py` does not change.
Fill a container that starts `hidden` and remove the attribute.

## Talking through AppState

Views never call each other. They read `AppState` and call its methods; it
notifies listeners (`state.subscribe(listener, *topics)`) by topic:

| Topic | When | Fields |
|---|---|---|
| `DOCUMENT` | the pattern changed: edit, undo, redo, load, new | `state.document`, `state.editor.can_undo` / `can_redo` |
| `VIEW` | UI state changed | `active_slot`, `tool` (`"cross"`/`"back"`/`"unpick"`), `edit_target` (`"unit"`, `"top"`, `"bottom"`, `"left"`, `"right"`, `"top_left"`, `"top_right"`, `"bottom_left"`, `"bottom_right"`), `mode` (`"edit"`/`"preview"`) |
| `STATUS` | a message for the user | `status` (i18n key and values); the shell shows it in the toast |
| `LANGUAGE` | the language changed | rebuild any text made in Python with `t(key, ...)` |

- Change the document only with `state.edit(lambda editor: editor.<method>(...))`
  (one undo step), or `begin_stroke()` / `end_stroke()` around a drag.
  `state.paint_cell` / `erase_cell` edit the current `edit_target`.
- `state.load(document)` (chunk 6) replaces the pattern, clears the history and
  goes back to the unit.
- `set_tool`, `set_edit_target` (both also switch to edit mode), `set_mode`,
  `select_slot` and `set_status` change UI state. The labels of edit targets
  are in `state.TARGET_LABEL_KEYS`.
- Calls across chunks that are not state:
  - `kvale_web.panels.lines.open_lines_dialog(axis=None, index=None, *, remove=False)`
    opens the rows and columns dialog (chunk 4's ruler popover "More options …").
    `open_lines_dialog("row", 4)` preselects row 5 (0-based `index`; for adding,
    the gap before which the new row goes) on "Add";
    `open_lines_dialog("column", 0, remove=True)` preselects column 1 on "Remove".
    Without arguments it opens as last used.
  - The thread list for the PNG (chunk 6): `thread_rows(document)` from
    `kvale_web.panels.colour_model` (no DOM; one `ColourInfo` per thread or own
    colour that the stitches use) and `row_text(info)` from
    `kvale_web.panels.thread_key` (`("DMC 321", "Red")` in the current language).
- Thread colours: a colour is a thread reference (`"dmc:321"`) or an own
  colour; brands are data in `kvale.core.threads` and the references are
  stored in `PatternDocument.palette_threads` (optional, see that module).
  Never show a bare code: use `thread.code` ("DMC 321").
- `#stage` carries `data-mode` and `data-target`; CSS hides `.edit-only` and
  `.preview-only` parts by mode.
- Keyboard shortcuts: `shortcuts.register("ctrl+s", handler)` in your own module.

## Installable, offline app and guide (chunk 7)

Plain JavaScript, so it works before Python has started:

- `sw.js`: the service worker. `tools/build_site.py` fills in the list of site
  files, a version (a hash of them) and the CDN cache name, and writes
  `manifest.webmanifest` with colours from `tokens.css`. Site files are cached
  when the worker installs; PyScript, Pyodide, Pillow and the fonts are cached
  on the first visit. A new version waits until the user presses "Reload".
- `pwa.js` and `pwa.css`: registering the worker, the "new version" toast
  (`#update-toast`), the install button (`#install-app`), and the help button
  (`#help-open`) that opens `guide/<language>.html` in `<dialog id="help-dialog">`.
  Strings: `pwa.*`, `help.*` (in the HTML with `data-i18n`, translated by Python).
- `guide/`: the user guide in nb, en and it. Screenshots are made with
  `python tools/guide_screenshots.py`; icons with `python tools/make_icons.py`.
- `window.kvaleOffline === "ready"` once the CDN files are cached (for tests).

## Tests

- `tests/test_web_state.py`: `AppState` in plain CPython. Add tests for new state here.
- `tests/test_web_i18n.py`: the three language files match each other and the
  approved design, and every key used in `index.html` or `kvale_web` exists.
  Reference strings by key only; a key the app needs that the design lacks goes
  in all three files and in "app only" in `docs/design/strings.md`.
- `tests/test_web_browser.py` (`pytest -m browser`): the real app in Chromium.
