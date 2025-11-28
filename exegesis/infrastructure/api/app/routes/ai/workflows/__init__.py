"""Composable router for AI workflows."""

from __future__ import annotations

from fastapi import APIRouter

from exegesis.application.facades import telemetry  # noqa: F401

from . import chat, exports, features, flows, llm, perspectives, settings, user_preferences
from .guardrails import (
    DEFAULT_REFUSAL_MESSAGE,
    extract_refusal_text,
    guardrail_advisory,
    guardrail_http_exception,
)

router = APIRouter()
router.include_router(features.router)
router.include_router(chat.router)
router.include_router(llm.router)
router.include_router(exports.router)
router.include_router(flows.router)
router.include_router(perspectives.router)

settings_router = APIRouter()
settings_router.include_router(settings.router)
settings_router.include_router(user_preferences.router)

__all__ = [
    "router",
    "settings_router",
    "DEFAULT_REFUSAL_MESSAGE",
    "guardrail_http_exception",
    "guardrail_advisory",
    "extract_refusal_text",
]
