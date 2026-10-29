"""Text for colours and lists, in the current language (uses ``t``).

A thread code is never shown alone: always with its brand, as "DMC 321".
"""

from __future__ import annotations

from kvale_web.i18n import t
from kvale_web.panels.colour_model import ColourInfo


def code_text(info: ColourInfo) -> str:
    """"DMC 321", or "Own colour"."""
    if info.code is None:
        return t("colours.own")
    return t("thread.code", system=info.code[0], code=info.code[1])


def full_text(info: ColourInfo) -> str:
    """"DMC 321 – Red", or "Own colour #c72b3b"."""
    if info.code is None:
        return f"{t('colours.own')} {info.hex_colour}"
    return f"{code_text(info)} – {info.name}" if info.name else code_text(info)


def slot_text(infos: list[ColourInfo]) -> str:
    """Short description of a slot: its thread, or "3 colours in turn"."""
    return t("colours.many", n=len(infos)) if len(infos) > 1 else code_text(infos[0])


def join_list(items: list[str]) -> str:
    """"a, b and c" in the current language."""
    if len(items) <= 1:
        return items[0] if items else ""
    return ", ".join(items[:-1]) + t("list.and") + items[-1]
