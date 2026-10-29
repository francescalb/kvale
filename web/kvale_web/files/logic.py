"""The browser-free part of the file views: reading and writing pattern files,
file names, unsaved-change tracking, the autosave record and patterns given in
the page URL.

Nothing here imports ``js`` or ``pyscript``, so it is tested in plain CPython
(``tests/test_web_files.py``).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import re
import zlib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal
from urllib.parse import parse_qs, unquote, urlsplit

from kvale.core.model import CORNER_FORMAT_VERSION, PatternDocument

JSON_EXTENSION = ".json"
PNG_EXTENSION = ".png"
# Characters most file systems refuse in a file name.
_UNSAFE_NAME = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')
# Bundled examples (``examples/<name>.json`` in the site): plain lower-case names only.
_EXAMPLE_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

AUTOSAVE_KEY = "kvale-autosave"
AUTOSAVE_VERSION = 1

# The largest image side in pixels; bigger bands get smaller squares.
PNG_MAX_SIDE = 8000
PNG_CELL_SIZE = 16
PNG_MIN_CELL_SIZE = 4


# Reading and writing ---------------------------------------------------


class OpenError(ValueError):
    """A pattern file could not be read; ``key`` is the i18n message to show."""

    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


def serialize(document: PatternDocument) -> str:
    """The text of a saved pattern file (the same as the desktop app writes)."""
    return json.dumps(document.to_dict(), indent=2)


def parse_document(text: str) -> PatternDocument:
    """Read a pattern file of any format version the core reads (up to 5).

    Raises ``OpenError`` with ``file.error.tooNew`` for a file from a newer
    Kvale, and ``file.error.notPattern`` for anything else that is not a pattern.
    """
    try:
        data = json.loads(text)
    except (ValueError, RecursionError) as error:
        raise OpenError("file.error.notPattern") from error
    if not isinstance(data, dict):
        raise OpenError("file.error.notPattern")
    version = data.get("format_version")
    if version is not None:
        try:
            too_new = int(version) > CORNER_FORMAT_VERSION
        except (TypeError, ValueError) as error:
            raise OpenError("file.error.notPattern") from error
        if too_new:
            raise OpenError("file.error.tooNew")
    try:
        return PatternDocument.from_dict(data)
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise OpenError("file.error.notPattern") from error


def fingerprint(text: str) -> str:
    """A short hash of a serialized pattern, to tell whether it changed."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


# File names ------------------------------------------------------------


def stem_of(file_name: str) -> str:
    """The pattern name of a file or URL path: no folders, no ``.json``."""
    name = unquote(file_name).replace("\\", "/").rsplit("/", 1)[-1].strip()
    if name.lower().endswith(JSON_EXTENSION):
        name = name[: -len(JSON_EXTENSION)]
    return name.strip()


def file_name(stem: str | None, extension: str, fallback: str) -> str:
    """A safe download name: ``<stem><extension>``, or the fallback name when untitled."""
    base = _UNSAFE_NAME.sub("-", (stem or "").strip()).strip(" .-")
    if not base:
        base = _UNSAFE_NAME.sub("-", fallback.strip()).strip(" .-") or "kvale"
    return base + extension


# Unsaved changes -------------------------------------------------------


class DocSession:
    """The open pattern's name and whether it has changes not saved to a file.

    ``name`` is ``None`` for a new, untitled pattern. Changes are found by
    comparing a fingerprint of the current document with the one at the last
    open or save, so undoing back to the saved state counts as saved again.
    """

    def __init__(self, document: PatternDocument, name: str | None = None) -> None:
        self.name = name
        self.saved_fingerprint = fingerprint(serialize(document))

    def mark_saved(self, document: PatternDocument, name: str | None = None) -> None:
        """The document was opened or saved (under ``name``, if given)."""
        if name is not None:
            self.name = name
        self.saved_fingerprint = fingerprint(serialize(document))

    def reset(self, document: PatternDocument, name: str | None) -> None:
        """A different pattern is now open (new, opened or restored)."""
        self.name = name
        self.saved_fingerprint = fingerprint(serialize(document))

    def is_dirty(self, document: PatternDocument) -> bool:
        return fingerprint(serialize(document)) != self.saved_fingerprint

    def display_name(self, untitled: str) -> str:
        return untitled if self.name is None else self.name + JSON_EXTENSION


# Autosave --------------------------------------------------------------


@dataclass(frozen=True)
class Autosave:
    """The pattern kept in browser storage between visits."""

    document: PatternDocument
    name: str | None
    saved_fingerprint: str  # of the last file save/open, to keep the unsaved marker
    time_ms: float  # when it was written (JavaScript time)


def autosave_payload(
    document_text: str, name: str | None, saved_fingerprint: str, time_ms: float
) -> str:
    """The text stored in browser storage for the current pattern."""
    return json.dumps(
        {
            "kvale_autosave": AUTOSAVE_VERSION,
            "name": name,
            "saved": saved_fingerprint,
            "time": time_ms,
            "document": json.loads(document_text),
        },
        separators=(",", ":"),
    )


def read_autosave(text: str | None) -> Autosave | None:
    """The stored autosave, or None if there is none or it cannot be read."""
    if not text:
        return None
    try:
        data = json.loads(text)
        if not isinstance(data, dict) or data.get("kvale_autosave") != AUTOSAVE_VERSION:
            return None
        document = parse_document(json.dumps(data["document"]))
        name = data.get("name")
        return Autosave(
            document=document,
            name=str(name) if name else None,
            saved_fingerprint=str(data.get("saved", "")),
            time_ms=float(data.get("time", 0)),
        )
    except (ValueError, KeyError, TypeError):
        return None


# Patterns given in the page URL ---------------------------------------


@dataclass(frozen=True)
class UrlSource:
    """Where to find the pattern named in the page URL.

    - ``example``: a bundled example, ``?example=flower-band`` (``value`` is the name);
    - ``file``: a pattern file to fetch, ``?file=<url>`` (same origin or CORS);
    - ``data``: the pattern itself, ``#data=<base64url of zlib-compressed JSON>``.
    """

    kind: Literal["example", "file", "data"]
    value: str

    @property
    def name(self) -> str | None:
        if self.kind == "example":
            return self.value
        if self.kind == "file":
            return stem_of(urlsplit(self.value).path) or None
        return None

    def fetch_url(self) -> str:
        """The URL to fetch (relative to the page) for ``example`` and ``file``."""
        if self.kind == "example":
            return f"examples/{self.value}{JSON_EXTENSION}"
        return self.value


def url_source(search: str, hash_part: str) -> UrlSource | None:
    """The pattern named by the query string (``?...``) or fragment (``#...``)."""
    query = parse_qs(search.lstrip("?"))
    example = (query.get("example") or [""])[0].strip()
    if example:
        return UrlSource("example", example) if _EXAMPLE_NAME.match(example) else None
    for key in ("file", "pattern"):
        url = (query.get(key) or [""])[0].strip()
        if url:
            scheme = urlsplit(url).scheme.lower()
            return UrlSource("file", url) if scheme in ("", "http", "https") else None
    fragment = parse_qs(hash_part.lstrip("#"))
    data = (fragment.get("data") or [""])[0].strip()
    if data:
        return UrlSource("data", data)
    return None


def encode_data_hash(document_text: str) -> str:
    """``data=...`` for a ``#`` link that holds the whole pattern."""
    compact = json.dumps(json.loads(document_text), separators=(",", ":"))
    packed = base64.urlsafe_b64encode(zlib.compress(compact.encode("utf-8"), 9))
    return "data=" + packed.decode("ascii").rstrip("=")


def decode_data_hash(value: str) -> str:
    """The pattern text in a ``#data=`` value; raises ``OpenError`` if it is damaged."""
    try:
        padded = value + "=" * (-len(value) % 4)
        packed = base64.b64decode(padded, altchars=b"-_", validate=True)
        # Patterns are small; refuse anything that inflates beyond 20 MB, and
        # a stream that stops early (a link cut short when copied).
        inflater = zlib.decompressobj()
        raw = inflater.decompress(packed, 20_000_000)
        if inflater.unconsumed_tail or not inflater.eof:
            raise OpenError("file.error.notPattern")
        return raw.decode("utf-8")
    except (binascii.Error, zlib.error, UnicodeDecodeError, ValueError) as error:
        if isinstance(error, OpenError):
            raise
        raise OpenError("file.error.notPattern") from error


# PNG export ------------------------------------------------------------


def png_cell_size(width: int, height: int) -> int:
    """Pixels per square, so the image of a ``width`` × ``height`` band stays a sane size."""
    longest = max(width, height, 1)
    return max(PNG_MIN_CELL_SIZE, min(PNG_CELL_SIZE, PNG_MAX_SIDE // longest))


def render_png(
    document: PatternDocument,
    key_rows: Sequence[tuple[str, str]] = (),
    key_title: str = "",
) -> bytes:
    """The whole band (ends, corners and backstitch included) as PNG bytes.

    ``key_rows`` are the threads the pattern uses, as ``(screen colour, text)``
    pairs such as ``("#c72b3b", "DMC 321 – Red")``; they are listed under the
    band with ``key_title`` above them (see ``kvale.core.render_image_with_key``).
    Needs Pillow; in the browser call ``ensure_pillow()`` first.
    """
    from kvale.core import build_colour_grid, render_image_with_key

    grid = build_colour_grid(document)
    height = len(grid)
    width = len(grid[0]) if height else 0
    image = render_image_with_key(
        document, key_rows, title=key_title, cell_size=png_cell_size(width, height)
    )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
