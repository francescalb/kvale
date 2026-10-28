# PyScript toolkit test: findings

PyScript 2026.7.3 with Pyodide 314.0.3 (CPython 3.14) and Pillow 12.2.0.

The app ran as a static site served by `python -m http.server`. It was driven by
headless Chromium through Playwright (`check.py`) and showed no console errors.
Every prototype feature worked on the first run.

Screenshots:
- `spikes/pyscript/screenshot.png`: editor after a JSON round trip, English
- `spikes/pyscript/screenshot-edit.png`: Norwegian, mirror_x and mirror_y, seed borders, hover tint
- `spikes/pyscript/screenshot-preview.png`: 6×2 repeat preview
- `spikes/pyscript/screenshot-mobile.png`: 390 px wide touch emulation, Italian chosen from the browser locale, rotate_180

## Numbers

All numbers come from headless Chromium on a desktop with an i5-3570K (2012) and
a home connection. They loaded from the CDN, with a cold cache on first load.

| Measure | Result |
|---|---|
| First-load download | **7.5 MB** in 29 requests: `pyodide.asm.wasm` 3.4 MB, `python_stdlib.zip` 2.5 MB, Pillow wheel 1.0 MB, `pyodide.asm.mjs` 0.26 MB, micropip 0.11 MB, PyScript core about 0.1 MB, the app about 0.05 MB |
| First load, until the app is interactive | 4.7–7.4 s (depends on the network) |
| Repeat load (HTTP cache, 0 bytes transferred) | about **3.0 s**. This is Pyodide start-up time, not download time |
| Edit redraw, 12×12 | 1.4–2.1 ms (median) |
| Click to repaint, measured by Playwright | about 10 ms median |
| Hover highlight redraw | about 1–2 ms, so per-pointermove redraws are fine |
| Preview redraw, 12×12 unit with 6×2 repeats | 6.7 ms |

Stress test (`window.kvaleBench`): 3 symmetry operations, 1/8 of the cells seeded
at random, times in ms.

| Unit, repeats | build_colour_grid | edit redraw | preview redraw | find_source_mark | PNG export |
|---|---|---|---|---|---|
| 24×24, 6×2 | 8 | 13 | 17 | 0.5 | 105 |
| 48×48, 8×4 | 29 | 15 | 43 | 8 | 905 |
| 100×100, 10×4 | 137 | 58 | 223 | 34 | 4 900 |

Python→JS calls are expensive. The first preview drew one `fillRect` per cell and
needed **2 000 ms** at 100×100×10×4 (400 000 cells). Building one RGBA buffer in
Python and passing it to the canvas with a single `putImageData` call brought
this down to 223 ms. That is roughly 137 ms in the pure-Python
`build_colour_grid` and the rest in packing the buffer. Large documents will
need patterns like this. Pyodide runs Python at roughly 1–2× native CPython
speed, so the core algorithms themselves are fine.

PNG export at the largest size makes a 16 000 × 6 400 px image (100 Mpx), which
takes about 5 s. A desktop would also be slow here. Either the export cell size
should go down for big patterns, or the export should run in a worker.

## Lines of code

| Kind | Lines |
|---|---|
| Python (`main.py`, including about 30 lines of benchmark hook) | 484 |
| HTML | 71 |
| CSS | 153 |
| JavaScript | **0** (only the `<script src=".../core.js">` loader tag) |
| TOML config | 12 |
| i18n JSON | 3 × 22 |
| Test script (Python, Playwright) | 171 |

## What was easy

- **Reusing the core unchanged.** The `[files]` table in `pyscript.toml` maps
  `../../src/kvale/...` into the virtual filesystem, and `import kvale.core`
  then works. `expand_marks`, `build_colour_grid`, `render_image` (Pillow) and
  `to_dict`/`from_dict` all ran without any changes.
- **The DOM is a Python object.** `document.getElementById(...)`,
  `canvas.getContext("2d")`, `ctx.fillRect(...)`, `event.button` and
  `event.preventDefault()` work as in JS, with Python syntax. Event handlers are
  ordinary Python functions wrapped in `create_proxy`.
- **Pointer events.** One code path covers mouse, touch and pen:
  `pointerdown`/`move`/`up`, `setPointerCapture` for drag painting, and
  `touch-action: none`. Right-click erase works after cancelling `contextmenu`.
  Touch taps and the eraser toggle worked under mobile emulation.
- **Downloads and the file picker.** A Blob and an `<a download>` give PNG and
  JSON downloads. A hidden `<input type=file>` with an `async def` handler and
  `await file.text()` loads JSON. Together this is about 30 lines.
- **i18n.** `data-i18n` attributes in the HTML, one JSON file per language
  fetched with `pyscript.fetch`, and a small `t(key, **values)` helper. The
  language is picked from `localStorage`, then `navigator.language`, then English.
- **Keyboard shortcuts.** One `keydown` listener on `document`. `Ctrl+S` and
  `Ctrl+O` can call `preventDefault()` synchronously because the code runs on
  the main thread.
- **Styling.** Plain CSS, because the widgets are real HTML elements. Light/dark
  mode and a phone layout took a few lines each.
- **No build step.** The static folder is the deployment.

## What was hard, awkward or a risk

- **Start-up cost.** Users see a spinner for 3–7 s on every visit, about 3 s
  even with a warm cache, because the CPython interpreter has to boot.
  `python_stdlib.zip` plus the wasm come to about 6 MB before any app code runs.
  This is the main user-facing cost. A loading screen made of plain HTML and CSS
  hides it reasonably well.
- **Pillow is required for start-up.** `kvale/core/__init__.py` and
  `renderer.py` import PIL at module level, so the Pillow wheel (1 MB) and its
  load time are paid before the first paint, although Pillow is only needed for
  PNG export. **Core note:** if `from PIL import ...` moved inside
  `render_image()` (or into a separate exporter module), Pillow could be loaded
  lazily on the first export with `micropip`/`pyodide.loadPackage`. Alternatively
  the browser could export PNG with `canvas.toBlob`. Nothing in core actually
  blocked the spike.
- **FFI granularity.** Each Python→JS call costs about a microsecond or more.
  Per-cell canvas calls are fine for one unit but not for big previews; see the
  buffer trick above. Drawing code needs to be written with this in mind.
- **Proxy lifetime.** Every Python callable handed to JS needs `create_proxy`,
  which is never freed unless destroyed by hand. That is fine for static
  bindings. Dynamic UIs that rebuild widgets, such as the palette here or a
  future sequence editor, leak a little unless proxies are tracked and destroyed.
- **No widget or component model.** PyScript gives you the DOM and nothing else.
  Panels such as the sequence editor, colour slots and grid settings mean
  creating elements by hand (`createElement`, `appendChild`, listeners) or
  writing the HTML statically and binding to it. The newer `pyscript.web` module
  wraps this more pythonically, but it was not tried here. Expect to write a
  small helper layer of your own.
- **Errors show up late.** Python exceptions inside event handlers appear in the
  browser console (and PyScript's error banner). The editor gives no type
  checking for the JS side; for example, `ctx.fillRect` is untyped.
- **Package cache.** The PyScript 2026.7.3 release notes say the IndexedDB
  package cache is force-disabled when the config contains local files, which
  this spike's config does. Repeat loads still came from the browser HTTP cache
  (0 bytes), so this made no difference here.
- **Deployment layout.** The page loads `../../src/...`, so GitHub Pages has to
  publish the repository root, or a tiny CI step has to copy `src/kvale` next to
  the page. Either is trivial.

## Remaining features in docs/PLAN.md

| Feature | Assessment |
|---|---|
| Hover row/column insert | **Fine.** Hover redraw is 1–2 ms. This can be drawn on the canvas as in Tkinter, or done with absolutely positioned HTML buttons over the canvas, which are easier to style and are accessible |
| Sequence editor (1–24 colours per slot) | **Doable, mostly DOM work.** `<input type=color>` is native and works from Python, and a `<dialog>` element gives a modal for free. No obstacle, but every bit of UI is hand-built |
| Offline / PWA with a service worker | **Feasible, but needs a little JavaScript.** A service worker must be a JS file (Python cannot run there), which means about 30 lines of cache-first fetch handling plus `manifest.webmanifest`. Self-hosting is cleaner than caching the CDN: PyScript publishes an offline bundle, and the interpreter can be pointed at a local Pyodide copy. That adds about 8 MB of static files to the Pages site, plus the Pillow wheel |
| Keyboard shortcuts | **Ctrl+S and Ctrl+O work** (tested). **Ctrl+N cannot be intercepted** in a normal browser tab (Chrome reserves Ctrl+N, Ctrl+T and Ctrl+W). It does work in an installed PWA window. This is a browser limit and applies to Flet too. Suggest Alt+N or a toolbar button in a tab |
| Right-click | **Works** (`contextmenu` cancelled on the canvas only) |
| Undo/redo, autosave | Pure Python plus `localStorage`; no obstacle |
| Background colour control | `<input type=color>`; trivial |
| Large grids (up to 100×100 unit, 100 repeats) | Needs care: buffer-based drawing, and a worker or reduced cell size for PNG export. 100 × 100 repeats of a 100×100 unit is 100 M cells, which is too much for any toolkit to preview naively |

## Verdict

PyScript is a **good fit** for Kvale. It keeps the project almost entirely in
Python and runs the existing core unchanged. Its output is a plain static
folder: no build, no Node, no JS, and the UI is real HTML/CSS, which is easy to
make look modern and is accessible. The canvas, pointer, keyboard, file and
download APIs are all reachable from Python with little friction, and painting
feels instant.

The costs are:
- the start-up wait (about 3 s warm, 5–7 s cold, 7.5 MB);
- building the UI by hand with no widget library;
- a small, unavoidable JS service worker for offline use.

None of these is a blocker for a pattern-design tool that people open
deliberately.
