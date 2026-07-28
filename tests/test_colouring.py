from collections.abc import Callable

from kvale.core.colouring import resolve_colour_index
from kvale.core.model import ColourRule


def _assert_raises_with_message(callable_obj: Callable[[], object], expected_message: str) -> None:
    try:
        callable_obj()
    except ValueError as error:
        assert expected_message in str(error)
        return
    raise AssertionError("Expected ValueError was not raised")


def test_colour_sequence_can_have_different_period_from_geometry() -> None:
    rule = ColourRule(mode="sequence", sequence=[0, 1, 2, 1, 3], advance="unit_x")
    indices = [resolve_colour_index(0, x, 0, 0, 0, rule, 4) for x in range(7)]
    assert indices == [0, 1, 2, 1, 3, 0, 1]


def test_fixed_mode_applies_offset_and_wraps() -> None:
    rule = ColourRule(mode="fixed", offset=2)
    assert resolve_colour_index(3, 0, 0, 0, 0, rule, 4) == 1


def test_unit_cycle_mode_uses_unit_coordinates() -> None:
    rule = ColourRule(mode="unit_cycle", ax=2, ay=1)
    # 1 + 2*3 + 1*2 = 9 -> 9 % 5 = 4
    assert resolve_colour_index(1, 3, 2, 0, 0, rule, 5) == 4


def test_cell_cycle_mode_uses_cell_coordinates() -> None:
    rule = ColourRule(mode="cell_cycle", ax=1, ay=2)
    # 2 + 1*4 + 2*3 = 12 -> 12 % 7 = 5
    assert resolve_colour_index(2, 0, 0, 4, 3, rule, 7) == 5


def test_sequence_mode_rejects_empty_sequence() -> None:
    rule = ColourRule(mode="sequence", sequence=[])
    _assert_raises_with_message(
        lambda: resolve_colour_index(0, 0, 0, 0, 0, rule, 4),
        "may not be empty",
    )


def test_sequence_mode_rejects_unknown_advance() -> None:
    rule = ColourRule(mode="sequence", sequence=[0, 1], advance="unknown")
    _assert_raises_with_message(
        lambda: resolve_colour_index(0, 0, 0, 0, 0, rule, 4),
        "Unknown colour sequence advance",
    )


def test_unknown_mode_is_rejected() -> None:
    rule = ColourRule(mode="unsupported")
    _assert_raises_with_message(
        lambda: resolve_colour_index(0, 0, 0, 0, 0, rule, 4),
        "Unknown colour rule mode",
    )
