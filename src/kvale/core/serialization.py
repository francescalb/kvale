from __future__ import annotations

import json
from pathlib import Path

from kvale.core.model import PatternDocument


def save_document(document: PatternDocument, path: Path) -> None:
    path.write_text(json.dumps(document.to_dict(), indent=2), encoding="utf-8")


def load_document(path: Path) -> PatternDocument:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Pattern file must contain a JSON object")
    return PatternDocument.from_dict(data)
