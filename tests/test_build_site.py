"""Tests for tools/build_site.py (the static web app build)."""

from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path
from types import ModuleType

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
    assert "kvale_web/state.py" in files
    assert "main.py" not in files
    # Every listed file exists in the build, and nothing from the Tkinter GUI is shipped.
    assert all((out / path).is_file() for path in files)
    assert not any(path.startswith("kvale/gui") for path in files)
