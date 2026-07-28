from kvale.core.model import Mark, PatternDocument


def test_document_round_trip() -> None:
    original = PatternDocument(motif=[Mark(2, 3, 1)])
    restored = PatternDocument.from_dict(original.to_dict())
    assert restored == original


def test_document_round_trip_with_palette_sequences() -> None:
    original = PatternDocument(
        palette=["#ff0000", "#000000"],
        palette_sequences=[["#ff0000", "#0000ff"], ["#000000"]],
        use_palette_sequence=True,
    )
    data = original.to_dict()
    assert "palette" not in data

    restored = PatternDocument.from_dict(data)
    assert restored.use_palette_sequence is True
    assert restored.palette_sequences == original.palette_sequences
    assert restored == original
