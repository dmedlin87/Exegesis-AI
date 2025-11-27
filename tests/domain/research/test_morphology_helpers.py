from __future__ import annotations

import pytest

from exegesis.domain.research import morphology as morphology_module
from exegesis.domain.research.morphology import MorphToken, fetch_morphology


def test_morph_token_defaults() -> None:
    token = MorphToken(osis="John.1.1", surface="\u1f18\u03bd")

    assert token.lemma is None
    assert token.morph is None
    assert token.gloss is None
    assert token.position is None


def test_fetch_morphology_builds_tokens_from_dataset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = {
        "John.1.1": [
            {
                "surface": "\u1f18\u03bd",
                "lemma": "\u1f10\u03bd",
                "morph": "PREP",
                "gloss": "in",
                "position": 1,
            },
            {
                "surface": "\u1f00\u03c1\u03c7\u1fc7",
            },
        ]
    }

    monkeypatch.setattr(morphology_module, "morphology_dataset", lambda: dataset)

    tokens = fetch_morphology("John.1.1")

    assert [token.surface for token in tokens] == ["\u1f18\u03bd", "\u1f00\u03c1\u03c7\u1fc7"]

    first, second = tokens
    assert first.lemma == "\u1f10\u03bd"
    assert first.morph == "PREP"
    assert first.gloss == "in"
    assert first.position == 1

    assert second.lemma is None
    assert second.morph is None
    assert second.gloss is None
    assert second.position is None


def test_fetch_morphology_returns_empty_list_for_missing_osis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(morphology_module, "morphology_dataset", lambda: {})

    assert fetch_morphology("John.9.9") == []
