"""Facade helpers exposing research application services."""
from __future__ import annotations

from typing import Callable

from exegesis.application.interfaces import SessionProtocol
from exegesis.application.services import ApplicationContainer
from exegesis.application.research import ResearchService
from exegesis.domain.research import (
    HypothesisDraft,
    ResearchNoteDraft,
    ResearchNoteEvidenceDraft,
)
__all__ = [
    "ResearchService",
    "ResearchNoteDraft",
    "ResearchNoteEvidenceDraft",
    "HypothesisDraft",
    "get_research_service",
    "set_application_resolver",
]


_application_resolver: Callable[[], ApplicationContainer] | None = None


def set_application_resolver(resolver: Callable[[], ApplicationContainer]) -> None:
    """Register the resolver used to obtain the application container."""

    global _application_resolver
    _application_resolver = resolver


def _resolve_container() -> ApplicationContainer:
    if _application_resolver is None:
        raise RuntimeError("Application resolver has not been configured")
    return _application_resolver()


def get_research_service(session: SessionProtocol) -> ResearchService:
    """Return a research service bound to the provided session."""

    container = _resolve_container()
    return container.get_research_service(session)
