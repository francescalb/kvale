"""Interface languages: Norwegian Bokmål (nb), English (en) and Italian (it).

Strings live in ``i18n/<code>.json`` (flat key -> text, ``{name}`` placeholders).

- In HTML, give an element ``data-i18n="key"`` and its text is set by
  ``apply_translations()``. Use ``data-i18n-title`` / ``data-i18n-aria-label``
  / ``data-i18n-placeholder`` for those attributes.
- In Python, call ``t("key", name=value)``. Text built in Python must be
  rebuilt when the ``LANGUAGE`` topic is notified (see ``state.py``).

Missing keys fall back to English, then to the key itself, so a missing
translation is visible but never crashes the app.
"""

from __future__ import annotations

from pyscript import document, fetch, window

from kvale_web.dom import local_storage_get, local_storage_set, query_all

LANGUAGES = ("nb", "en", "it")
DEFAULT_LANGUAGE = "nb"
FALLBACK_LANGUAGE = "en"
STORAGE_KEY = "kvale-lang"
# data-* attribute suffix -> element attribute it translates
_ATTRIBUTES = {"title": "title", "aria-label": "aria-label", "placeholder": "placeholder"}

_cache: dict[str, dict[str, str]] = {}
_current = DEFAULT_LANGUAGE


def current_language() -> str:
    return _current


def t(key: str, **values: object) -> str:
    """Translate ``key`` into the current language and fill in ``{placeholders}``."""
    text = _cache.get(_current, {}).get(key)
    if text is None:
        text = _cache.get(FALLBACK_LANGUAGE, {}).get(key, key)
    try:
        return text.format(**values)
    except (KeyError, IndexError, ValueError):
        return text


def normalise_language(code: str | None) -> str | None:
    """Map a browser or stored language tag to a supported code, or None."""
    if not code:
        return None
    base = code.strip().lower().replace("_", "-").split("-")[0]
    base = {"no": "nb", "nn": "nb"}.get(base, base)
    return base if base in LANGUAGES else None


def initial_language() -> str:
    """Saved choice, then the browser language, then Norwegian."""
    stored = normalise_language(local_storage_get(STORAGE_KEY))
    if stored:
        return stored
    for code in list(window.navigator.languages or []) + [window.navigator.language]:
        found = normalise_language(str(code) if code else None)
        if found:
            return found
    return DEFAULT_LANGUAGE


async def _load(code: str) -> dict[str, str]:
    if code not in _cache:
        response = await fetch(f"i18n/{code}.json")
        if not response.ok:
            raise RuntimeError(f"Could not load i18n/{code}.json ({response.status})")
        data = await response.json()
        _cache[code] = {str(key): str(value) for key, value in data.items()}
    return _cache[code]


async def set_language(code: str) -> None:
    """Load and switch to ``code``, remember it, and translate the static HTML.

    The caller should then notify ``LANGUAGE`` so views rebuild their text.
    """
    global _current
    code = normalise_language(code) or DEFAULT_LANGUAGE
    if FALLBACK_LANGUAGE not in _cache:
        await _load(FALLBACK_LANGUAGE)
    await _load(code)
    _current = code
    document.documentElement.lang = code
    local_storage_set(STORAGE_KEY, code)
    apply_translations()


def apply_translations() -> None:
    """Set the text of every ``data-i18n`` element (and translated attributes)."""
    for element in query_all("[data-i18n]"):
        element.textContent = t(str(element.dataset.i18n))
    for suffix, attribute in _ATTRIBUTES.items():
        for element in query_all(f"[data-i18n-{suffix}]"):
            element.setAttribute(attribute, t(str(element.getAttribute(f"data-i18n-{suffix}"))))
