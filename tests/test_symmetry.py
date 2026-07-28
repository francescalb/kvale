from collections.abc import Callable

from kvale.core.model import Mark
from kvale.core.symmetry import expand_marks, transform_point


def _assert_raises_with_message(callable_obj: Callable[[], object], expected_message: str) -> None:
    try:
        callable_obj()
    except ValueError as error:
        assert expected_message in str(error)
        return
    raise AssertionError("Expected ValueError was not raised")


def test_mirror_x() -> None:
    assert transform_point(1, 2, 8, 6, "mirror_x") == (6, 2)


def test_four_way_expansion() -> None:
    marks = expand_marks(
        [Mark(1, 1, 0)],
        width=6,
        height=6,
        operations=["identity", "mirror_x", "mirror_y", "rotate_180"],
    )
    assert {(mark.x, mark.y) for mark in marks} == {(1, 1), (4, 1), (1, 4), (4, 4)}


def test_horizontal_and_vertical_mirrors_are_combined() -> None:
    marks = expand_marks(
        [Mark(1, 1, 0)],
        width=6,
        height=6,
        operations=["identity", "mirror_x", "mirror_y"],
    )

    positions = {
        (mark.x, mark.y)
        for mark in marks
    }

    assert positions == {
        (1, 1),
        (4, 1),
        (1, 4),
        (4, 4),
    }


def test_rotate_90_transform_for_square_unit() -> None:
    assert transform_point(1, 2, 6, 6, "rotate_90") == (3, 1)


def test_square_only_operations_fail_for_non_square_unit() -> None:
    _assert_raises_with_message(
        lambda: transform_point(1, 1, 6, 4, "rotate_90"),
        "requires a square recurring unit",
    )
