from __future__ import annotations

from kvale.core.model import ColourRule


def resolve_colour_index(
    colour_slot: int,
    unit_x: int,
    unit_y: int,
    cell_x: int,
    cell_y: int,
    rule: ColourRule,
    palette_size: int,
) -> int:
    if palette_size < 1:
        raise ValueError("palette_size must be positive")

    if rule.mode == "fixed":
        value = colour_slot + rule.offset
    elif rule.mode == "unit_cycle":
        value = colour_slot + rule.ax * unit_x + rule.ay * unit_y + rule.offset
    elif rule.mode == "cell_cycle":
        value = colour_slot + rule.ax * cell_x + rule.ay * cell_y + rule.offset
    elif rule.mode == "sequence":
        if not rule.sequence:
            raise ValueError("Colour sequence may not be empty")
        positions = {
            "unit_x": unit_x,
            "unit_y": unit_y,
            "unit_xy": unit_x + unit_y,
            "cell_x": cell_x,
            "cell_y": cell_y,
        }
        if rule.advance not in positions:
            raise ValueError(f"Unknown colour sequence advance: {rule.advance}")
        value = colour_slot + rule.sequence[positions[rule.advance] % len(rule.sequence)]
        value += rule.offset
    else:
        raise ValueError(f"Unknown colour rule mode: {rule.mode}")

    return value % palette_size
