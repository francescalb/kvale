# Kvale PyScript spike (chunk 0, throwaway)

A small browser version of the Kvale editor written in Python with
[PyScript](https://pyscript.net). The prototype uses the real `kvale.core` without
changes. Results are in [FINDINGS.md](FINDINGS.md).

## Run

From the **repository root** (the page loads `../../src/kvale/core/*.py`):

```bash
python -m http.server 8000
```

Then open <http://localhost:8000/spikes/pyscript/>. You need no build step and no
JavaScript tooling. The site is fully static, so GitHub Pages can serve it as-is
when the repository root is published.

## Versions

| Component | Version |
|---|---|
| PyScript | 2026.7.3 (pinned in `index.html`, loaded from `pyscript.net/releases/2026.7.3/`) |
| Pyodide | 314.0.3 (bundled with that PyScript release; CPython 3.14) |
| Pillow (Pyodide package) | 12.2.0 |
| Playwright (only for `check.py`) | latest from pip, headless Chromium |

## Files

| File | Purpose |
|---|---|
| `index.html` | Static markup. Labels carry `data-i18n` keys. There is no hand-written JS |
| `pyscript.toml` | Loads Pillow and maps `src/kvale/**.py` into Pyodide's filesystem |
| `main.py` | The whole app: canvas drawing, pointer and keyboard events, i18n, downloads |
| `style.css` | Hand-written styles, including light/dark and a narrow-screen layout |
| `i18n/{nb,en,it}.json` | One flat key-to-string file per language, fetched when needed |
| `check.py` | Headless Playwright smoke test and measurements |

## Smoke test and measurements

```bash
python -m venv .venv && .venv/bin/pip install playwright && .venv/bin/playwright install chromium
python -m http.server 8765 &   # from repo root
.venv/bin/python spikes/pyscript/check.py http://localhost:8765/spikes/pyscript/
```

The test writes `screenshot.png`, `screenshot-edit.png` and `screenshot-preview.png`.

## Using it

- Left-click or tap paints with the active colour. Right-click erases, and so
  does the **Eraser** toggle (useful on touch screens). Drag to paint several cells.
- Clicking a generated copy recolours or erases the seed mark it came from.
  Seed marks have a dark inset border.
- Keyboard: `1`–`4` pick a colour, `E` toggles the eraser, `P` toggles the
  preview, `Ctrl+S` saves JSON and `Ctrl+O` opens JSON.
