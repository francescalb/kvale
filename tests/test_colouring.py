from kvale.core.colouring import resolve_colour_index
from kvale.core.model import ColourRule


def test_colour_sequence_can_have_different_period_from_geometry() -> None:
    rule = ColourRule(mode="sequence", sequence=[0, 1, 2, 1, 3], advance="unit_x")
    indices = [resolve_colour_index(0, x, 0, 0, 0, rule, 4) for x in range(7)]
    assert indices == [0, 1, 2, 1, 3, 0, 1]
