"""The interface strings in web/i18n/{nb,en,it}.json.

- All three files have the same keys and the same {placeholders} per key.
- They hold the approved wording: every key of the mockup's ``STR`` object
  (docs/design/mockup.html, the same tables as docs/design/strings.md), word
  for word, apart from the mockup-only ``mock.*`` keys.
- Every key that index.html or kvale_web uses exists.
"""

from __future__ import annotations

import ast
import json
import re
import string
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
LANGUAGES = ("nb", "en", "it")
# Keys the app needs that the mockup does not show (listed in strings.md too).
APP_ONLY_KEYS = {
    "canvas.hint.minimal",
    # Files (chunk 6)
    "file.untitled",
    "file.unsaved",
    "file.saveAs",  # chunk 8: the "Save as" button (owner's decision)
    "file.saveAs.hint",
    "file.confirmDiscard",
    "file.export.preparing",
    "file.error.notPattern",
    "file.error.tooNew",
    "file.error.fetch",
    "file.error.export",
    # Install, offline and the guide (chunk 7)
    "help.open",
    "help.open.hint",
    "help.title",
    "help.newTab",
    "help.close",
    "pwa.install",
    "pwa.install.hint",
    "pwa.update",
    "pwa.reload",
}


def load(code: str) -> dict[str, str]:
    data: dict[str, str] = json.loads((WEB / "i18n" / f"{code}.json").read_text("utf-8"))
    return data


STRINGS = {code: load(code) for code in LANGUAGES}


def placeholders(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def mockup_strings() -> dict[str, dict[str, str]]:
    text = (ROOT / "docs" / "design" / "mockup.html").read_text("utf-8")
    start = text.index("const STR = ") + len("const STR = ")
    end = text.index("\n};", start) + 2
    data: dict[str, dict[str, str]] = json.loads(text[start:end])
    return data


def test_same_keys_in_every_language() -> None:
    keys = set(STRINGS["nb"])
    for code in LANGUAGES:
        assert set(STRINGS[code]) == keys, code


@pytest.mark.parametrize("code", LANGUAGES)
def test_same_placeholders_and_valid_format(code: str) -> None:
    for key, text in STRINGS[code].items():
        assert placeholders(text) == placeholders(STRINGS["en"][key]), (code, key)
        text.format(**{name: "x" for name in placeholders(text)})  # no stray braces


@pytest.mark.parametrize("code", LANGUAGES)
def test_approved_wording_from_the_design(code: str) -> None:
    approved = {k: v for k, v in mockup_strings()[code].items() if not k.startswith("mock.")}
    ours = STRINGS[code]
    assert {k: ours.get(k) for k in approved} == approved
    assert set(ours) - set(approved) == APP_ONLY_KEYS


def test_app_only_keys_are_documented() -> None:
    doc = (ROOT / "docs" / "design" / "strings.md").read_text("utf-8")
    for key in APP_ONLY_KEYS:
        assert f"`{key}`" in doc


def html_keys() -> set[str]:
    html = (WEB / "index.html").read_text("utf-8")
    return set(re.findall(r'data-i18n(?:-[a-z-]+)?="([^"]+)"', html))


def python_keys() -> set[str]:
    """String literals in kvale_web that look like i18n keys ("namespace.name...")."""
    namespaces = {key.split(".")[0] for key in STRINGS["en"]}
    pattern = re.compile(r"^[a-z]+(\.[A-Za-z]+)+$")
    found = set()
    for path in (WEB / "kvale_web").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text("utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                value = node.value
                if pattern.match(value) and value.split(".")[0] in namespaces:
                    found.add(value)
    return found


def test_every_key_used_exists() -> None:
    used = html_keys() | python_keys()
    assert "canvas.hint.cross" in used and "colours.slot" in used  # the scan works
    assert used - set(STRINGS["en"]) == set()


def test_html_fallback_text_is_norwegian() -> None:
    """Text inside data-i18n elements is the nb string, shown until Python starts."""
    html = (WEB / "index.html").read_text("utf-8")
    for key, text in re.findall(r'data-i18n="([^"]+)"[^>]*>([^<]*)<', html):
        if text:
            assert text == STRINGS["nb"][key], key
