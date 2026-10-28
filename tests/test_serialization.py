from collections.abc import Callable

from kvale.core.model import Mark, PatternDocument


def _assert_raises_with_message(callable_obj: Callable[[], object], expected_message: str) -> None:
    try:
        callable_obj()
    except ValueError as error:
        assert expected_message in str(error)
        return
    raise AssertionError("Expected ValueError was not raised")


def test_document_round_trip() -> None:
    original = PatternDocument(
        motif=[Mark(2, 3, 1)],
        palette_sequences=[["#b1172b"], ["#2d7d32"], ["#f2c84b"], ["#1b1b1b"]],
    )
    restored = PatternDocument.from_dict(original.to_dict())
    assert restored == original


def test_document_round_trip_with_palette_sequences() -> None:
    original = PatternDocument(
        palette_sequences=[["#ff0000", "#0000ff"], ["#000000"]],
        use_palette_sequence=True,
    )
    data = original.to_dict()
    assert "palette" not in data

    restored = PatternDocument.from_dict(data)
    assert restored.use_palette_sequence is True
    assert restored.palette == ["#ff0000", "#000000"]
    assert restored.palette_sequences == original.palette_sequences
    assert restored == original


def test_document_requires_palette_sequences() -> None:
    _assert_raises_with_message(
        lambda: PatternDocument.from_dict({"palette": ["#ff0000"]}),
        "palette_sequences",
    )


def test_document_rejects_empty_palette_sequence_row() -> None:
    _assert_raises_with_message(
        lambda: PatternDocument.from_dict(
            {
                "palette_sequences": [[], ["#00ff00"]],
                "motif": [],
            }
        ),
        "non-empty list",
    )
