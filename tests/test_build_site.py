"""Tests for tools/build_site.py (the static web app build)."""

from __future__ import annotations

import importlib.util
import json
import re
import tomllib
from pathlib import Path
from types import ModuleType

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent


def _build_site() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_site", ROOT / "tools" / "build_site.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_files_table_lists_core_modules_and_package_data(tmp_path: Path) -> None:
    out = _build_site().build(tmp_path / "site")
    files = tomllib.loads((out / "pyscript.toml").read_text(encoding="utf-8"))["files"]
    core = ROOT / "src" / "kvale" / "core"
    for module in core.glob("*.py"):
        assert f"kvale/core/{module.name}" in files
    assert files["kvale/core/dmc_palette.json"] == "./kvale/core/dmc_palette.json"
    # The font of the thread list in the saved image.
    assert "kvale/core/fonts/AtkinsonHyperlegible-Regular.ttf" in files
    assert "kvale_web/state.py" in files
    assert "main.py" not in files
    # Every listed file exists in the build, and nothing from the Tkinter GUI is shipped.
    assert all((out / path).is_file() for path in files)
    assert not any(path.startswith("kvale/gui") for path in files)


def test_example_patterns_are_shipped(tmp_path: Path) -> None:
    out = _build_site().build(tmp_path / "site")
    assert (out / "examples" / "flower-band.json").read_bytes() == (
        ROOT / "examples" / "flower-band.json"
    ).read_bytes()
    assert not list((out / "examples").glob("*.png"))


# Installable, offline app (chunk 7) -------------------------------------------

LANGUAGES = ("nb", "en", "it")
NOT_CACHED = {"sw.js", ".nojekyll", "README.md"}


def _worker(out: Path) -> tuple[str, list[str], str]:
    """VERSION, PRECACHE and CDN_CACHE as written into _site/sw.js."""
    text = (out / "sw.js").read_text(encoding="utf-8")
    version = re.search(r'^const VERSION = "([^"]*)";', text, re.M)
    precache = re.search(r"^const PRECACHE = (\[.*?\]);", text, re.M | re.S)
    cdn = re.search(r'^const CDN_CACHE = "([^"]*)";', text, re.M)
    assert version and precache and cdn
    paths: list[str] = json.loads(precache.group(1))
    return version.group(1), paths, cdn.group(1)


def test_manifest_is_valid_and_uses_the_tokens(tmp_path: Path) -> None:
    module = _build_site()
    out = module.build(tmp_path / "site")
    manifest = json.loads((out / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifest["name"] == manifest["short_name"] == "Kvale"
    # Relative to the manifest, so the app works under /kvale/ on GitHub Pages.
    assert manifest["start_url"] == manifest["scope"] == manifest["id"] == "./"
    assert manifest["display"] == "standalone"
    colours = module.token_colours((ROOT / "web" / "tokens.css").read_text(encoding="utf-8"))
    assert manifest["theme_color"] == colours["surface"] == "#fbf8f2"
    assert manifest["background_color"] == colours["bg"] == "#f4efe6"
    purposes: dict[str, set[str]] = {}
    for icon in manifest["icons"]:
        path = out / icon["src"]
        assert path.is_file(), icon["src"]
        purposes.setdefault(icon["purpose"], set()).add(icon["sizes"])
        if icon["type"] == "image/png":
            size = int(icon["sizes"].split("x")[0])
            with Image.open(path) as image:
                assert image.size == (size, size)
    assert {"192x192", "512x512"} <= purposes["any"]
    assert purposes["maskable"] == {"192x192", "512x512"}
    html = (out / "index.html").read_text(encoding="utf-8")
    assert '<link rel="manifest" href="manifest.webmanifest">' in html
    assert '<script src="pwa.js"></script>' in html


def test_every_cached_path_exists_and_the_site_is_covered(tmp_path: Path) -> None:
    out = _build_site().build(tmp_path / "site")
    _, precache, _ = _worker(out)
    assert precache == sorted(set(precache))
    assert all((out / path).is_file() for path in precache)
    files = tomllib.loads((out / "pyscript.toml").read_text(encoding="utf-8"))["files"]
    for needed in [
        "index.html",
        "main.py",
        "pyscript.toml",
        "pwa.js",
        "manifest.webmanifest",
        "tokens.css",
        "icons/icon.svg",
        "guide/guide.css",
        "examples/flower-band.json",
        *files,
        *(f"i18n/{code}.json" for code in LANGUAGES),
        *(f"guide/{code}.html" for code in LANGUAGES),
    ]:
        assert needed in precache, needed
    # Every other site file is cached.
    every = {path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file()}
    assert every - set(precache) == NOT_CACHED


def test_version_and_cache_names_are_injected(tmp_path: Path) -> None:
    module = _build_site()
    out = module.build(tmp_path / "site")
    assert "__KVALE_" not in (out / "sw.js").read_text(encoding="utf-8")
    version, precache, cdn = _worker(out)
    assert re.fullmatch(r"[0-9a-f]{16}", version)
    template = (ROOT / "web" / "sw.js").read_text(encoding="utf-8")
    assert version == module.site_version(out, precache, template)
    index = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    release = re.search(r"pyscript\.net/releases/([^/]+)/core\.js", index)
    assert release and cdn == f"kvale-cdn-{release.group(1)}"
    # The same sources give the same version.
    assert _worker(module.build(tmp_path / "again"))[0] == version


def test_site_version_covers_paths_contents_and_worker(tmp_path: Path) -> None:
    site_version = _build_site().site_version
    (tmp_path / "a.txt").write_text("one", encoding="utf-8")
    first = site_version(tmp_path, ["a.txt"], "worker")
    assert site_version(tmp_path, ["a.txt"], "worker") == first
    assert site_version(tmp_path, ["a.txt"], "worker 2") != first
    (tmp_path / "a.txt").write_text("two", encoding="utf-8")
    assert site_version(tmp_path, ["a.txt"], "worker") != first


def test_guides_match_and_their_images_exist() -> None:
    guide = ROOT / "web" / "guide"
    sections = {}
    for code in LANGUAGES:
        html = (guide / f"{code}.html").read_text(encoding="utf-8")
        assert f'<html lang="{code}">' in html
        assert f'href="{code}.html" lang="{code}" hreflang="{code}" aria-current="page"' in html
        sections[code] = re.findall(r'<section id="([^"]+)"', html)
        for src in re.findall(r'<img src="([^"]+)"', html):
            assert (guide / src).is_file(), (code, src)
            assert src.startswith(f"img/{code}-"), (code, src)
        # Every table-of-contents link points at a section.
        assert set(re.findall(r'<li><a href="#([^"]+)"', html)) == set(sections[code])
    assert sections["nb"] == sections["en"] == sections["it"]
    assert len(sections["en"]) == 10
    # Screenshots are kept small.
    assert all(path.stat().st_size < 80_000 for path in (guide / "img").iterdir())
