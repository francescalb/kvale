from kvale.core.model import Mark
from kvale.core.symmetry import expand_marks, transform_point


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
