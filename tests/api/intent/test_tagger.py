"""Tests for the intent tagger helpers."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from exegesis.infrastructure.api.app.intent import tagger as intent_tagger
from exegesis.infrastructure.api.app.research.ai.router import RoutedGeneration


class StubRouter:
    def __init__(self, output: str):
        self.output = output
        self.model = SimpleNamespace(name="stub-model")

    def iter_candidates(self, *_, **__):
        yield self.model

    def execute_generation(
        self,
        *,
        workflow: str,
        model: object,
        prompt: str,
        temperature: float = 0.0,
        max_output_tokens: int = 8,
    ) -> RoutedGeneration:
        return RoutedGeneration(
            model=model,
            output=self.output,
            latency_ms=0.0,
            cost=0.0,
        )


def test_predict_returns_normalised_category() -> None:
    router = StubRouter("search\nReasoning notes")
    tagger = intent_tagger.IntentTagger(SimpleNamespace(), router=router)

    result = tagger.predict("Find verses about grace")

    assert isinstance(result, intent_tagger.IntentTag)
    assert result.intent == "SEARCH"
    assert result.stance is None
    assert result.confidence is None


def test_predict_handles_extended_category_names() -> None:
    router = StubRouter("contradiction_check (confidence: 0.9)")
    tagger = intent_tagger.IntentTagger(SimpleNamespace(), router=router)

    result = tagger.predict("Compare these passages")

    assert result.intent == "CONTRADICTION_CHECK"


def test_predict_raises_when_router_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    tagger = intent_tagger.IntentTagger(SimpleNamespace())
    monkeypatch.setattr(tagger, "_resolve_router", lambda: None)

    with pytest.raises(RuntimeError):
        tagger.predict("anything")


def test_get_intent_tagger_respects_feature_toggle() -> None:
    settings = SimpleNamespace(intent_tagger_enabled=False)
    assert intent_tagger.get_intent_tagger(SimpleNamespace(), settings) is None


def test_get_intent_tagger_handles_initialisation_failure(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    settings = SimpleNamespace(intent_tagger_enabled=True)

    def _failing_ctor(session: object) -> intent_tagger.IntentTagger:
        raise RuntimeError("boom")

    monkeypatch.setattr(intent_tagger, "IntentTagger", _failing_ctor)

    with caplog.at_level(logging.WARNING):
        assert intent_tagger.get_intent_tagger(SimpleNamespace(), settings) is None

    assert "Intent tagger could not be initialised" in caplog.text
