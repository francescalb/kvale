from kvale.core.model import Mark, PatternDocument


def test_document_round_trip() -> None:
    original = PatternDocument(motif=[Mark(2, 3, 1)])
    restored = PatternDocument.from_dict(original.to_dict())
    assert restored == original
