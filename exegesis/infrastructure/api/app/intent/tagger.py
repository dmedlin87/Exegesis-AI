"""Intent classification utilities powered by a semantic LLM router."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from exegesis.application.ports.ai_registry import GenerationError
from exegesis.application.prompts.routing import ROUTER_SYSTEM_PROMPT
from exegesis.infrastructure.api.app.research.ai.router import LLMRouterService, get_router
from exegesis.infrastructure.api.app.research.ai.registry import LLMRegistry

LOGGER = logging.getLogger(__name__)

_CATEGORY_NAMES = (
    "SEARCH",
    "CONTRADICTION_CHECK",
    "SUMMARIZE",
    "WORD_STUDY",
    "GENERAL_CHAT",
)
_CATEGORY_PATTERN = re.compile(r"\b(" + r"|".join(_CATEGORY_NAMES) + r")\b", re.IGNORECASE)


@dataclass(slots=True)
class IntentTag:
    """Structured representation of a classified chat intent."""

    intent: str
    stance: str | None = None
    confidence: float | None = None

    def to_payload(self) -> dict[str, Any]:
        """Return a serialisable representation of the tag."""

        payload: dict[str, Any] = {"intent": self.intent}
        if self.stance:
            payload["stance"] = self.stance
        if self.confidence is not None:
            payload["confidence"] = float(self.confidence)
        return payload


class IntentTagger:
    """Zero-shot intent classifier powered by the LLM router."""

    def __init__(
        self,
        session: Session,
        *,
        router: LLMRouterService | None = None,
        registry: LLMRegistry | None = None,
        model_hint: str | None = None,
    ) -> None:
        self._session = session
        self._router_override = router
        self._registry = registry
        self._model_hint = model_hint
        self._router: LLMRouterService | None = None

    def predict(self, message: str) -> IntentTag:
        """Predict an intent tag for the provided user message."""

        cleaned = (message or "").strip()
        if not cleaned:
            raise ValueError("message must be provided for intent tagging")

        router = self._resolve_router()
        if router is None:
            raise RuntimeError("LLM router unavailable for intent tagging")

        prompt = self._build_prompt(cleaned)
        for candidate in router.iter_candidates("intent_classification", self._model_hint):
            try:
                routed = router.execute_generation(
                    workflow="intent_classification",
                    model=candidate,
                    prompt=prompt,
                    temperature=0.0,
                    max_output_tokens=8,
                )
            except GenerationError as exc:
                LOGGER.debug(
                    "Intent tagging generation failed via %s",
                    getattr(candidate, "name", "<unknown>"),
                    exc_info=exc,
                )
                continue
            category = self._extract_category(routed.output)
            if category:
                return IntentTag(intent=category)

        raise RuntimeError("Failed to classify intent via LLM router")

    def _build_prompt(self, message: str) -> str:
        instruction = ROUTER_SYSTEM_PROMPT.strip()
        return (
            f"{instruction}\n\n"
            f"User message:\n{message}\n\n"
            "Category:"
        )

    def _extract_category(self, text: str) -> str | None:
        for line in text.splitlines():
            match = _CATEGORY_PATTERN.search(line)
            if match:
                return match.group(1).upper()
        # Fallback: try to strip punctuation and match direct value
        normalized = re.sub(r"[^A-Za-z_]", "", text).upper()
        return normalized if normalized in _CATEGORY_NAMES else None

    def _resolve_router(self) -> LLMRouterService | None:
        if self._router_override is not None:
            return self._router_override
        if self._router is not None:
            return self._router
        try:
            self._router = get_router(self._session, registry=self._registry)
        except Exception:  # pragma: no cover - router may be misconfigured in tests
            LOGGER.debug("Unable to resolve LLM router for intent tagging", exc_info=True)
            self._router = None
        return self._router


def get_intent_tagger(session: Session, settings: Any) -> IntentTagger | None:
    """Instantiate an intent tagger based on runtime settings."""

    enabled = bool(getattr(settings, "intent_tagger_enabled", False))
    if not enabled:
        return None

    try:
        return IntentTagger(session)
    except Exception as exc:  # pragma: no cover - surface as warning and fall back gracefully
        LOGGER.warning("Intent tagger could not be initialised: %s", exc)
        return None

