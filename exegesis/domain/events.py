"""Typed domain events for the Exegesis system.

This module defines strongly-typed event schemas that flow through
the event bus. Each event class is a frozen dataclass that:
- Enforces required fields at construction time
- Provides type hints for payload data
- Enables IDE autocompletion and static analysis
- Serializes to the standard DomainEvent envelope format

Usage:
    from exegesis.domain.events import IngestionCompletedEvent

    event = IngestionCompletedEvent(
        document_id="doc-123",
        source_url="https://example.com/doc.pdf",
        document_type="pdf",
    )
    event_bus.publish(event.to_domain_event())
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping
from uuid import UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class BaseEvent:
    """Base class for all typed domain events.

    Subclasses should define their specific payload fields
    and implement the EVENT_TYPE class attribute.

    Note: All fields use kw_only=True so subclasses can have required fields.
    """

    EVENT_TYPE: str = field(init=False, repr=False, default="exegesis.unknown")
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_payload(self) -> dict[str, Any]:
        """Convert event-specific fields to a serializable payload dict.

        Override this in subclasses to customize serialization.
        """
        from exegesis.application.ports.events import normalise_event_value

        payload = {}
        for field_name in self.__dataclass_fields__:
            if field_name in ("EVENT_TYPE", "occurred_at"):
                continue
            value = getattr(self, field_name)
            payload[field_name] = normalise_event_value(value)
        return payload

    def to_domain_event(self) -> "DomainEvent":
        """Convert to the standard DomainEvent envelope format."""
        from exegesis.application.ports.events import DomainEvent

        return DomainEvent(
            type=self.EVENT_TYPE,
            payload=self.to_payload(),
            occurred_at=self.occurred_at,
        )


# ============================================================================
# Ingestion Events
# ============================================================================

@dataclass(frozen=True, slots=True, kw_only=True)
class IngestionCompletedEvent(BaseEvent):
    """Fired when a document has been successfully ingested."""

    EVENT_TYPE: str = field(init=False, repr=False, default="exegesis.ingestion.completed")

    document_id: str | UUID
    source_url: str | None = None
    document_type: str | None = None
    title: str | None = None
    page_count: int | None = None
    passage_count: int | None = None
    frontmatter: Mapping[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"document_id": str(self.document_id)}
        if self.source_url:
            payload["source_url"] = self.source_url
        if self.document_type:
            payload["document_type"] = self.document_type
        if self.title:
            payload["title"] = self.title
        if self.page_count is not None:
            payload["page_count"] = self.page_count
        if self.passage_count is not None:
            payload["passage_count"] = self.passage_count
        if self.frontmatter:
            from exegesis.application.ports.events import normalise_event_value
            payload["frontmatter"] = normalise_event_value(self.frontmatter)
        return payload


@dataclass(frozen=True, slots=True, kw_only=True)
class IngestionFailedEvent(BaseEvent):
    """Fired when document ingestion fails."""

    EVENT_TYPE: str = field(init=False, repr=False, default="exegesis.ingestion.failed")

    source_url: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    document_type: str | None = None


# ============================================================================
# Discovery Events
# ============================================================================

@dataclass(frozen=True, slots=True, kw_only=True)
class DiscoveryRefreshedEvent(BaseEvent):
    """Fired when discoveries are refreshed for a user."""

    EVENT_TYPE: str = field(init=False, repr=False, default="exegesis.discoveries.refreshed")

    user_id: str
    discovery_count: int = 0
    duration_ms: float | None = None


# ============================================================================
# Topic Digest Events
# ============================================================================

@dataclass(frozen=True, slots=True, kw_only=True)
class TopicDigestGeneratedEvent(BaseEvent):
    """Fired when a topic digest is generated."""

    EVENT_TYPE: str = field(init=False, repr=False, default="exegesis.topic_digest.generated")

    digest_id: str | None = None
    topic_count: int = 0
    document_count: int = 0
    digest_data: Mapping[str, Any] | None = None


# ============================================================================
# Search Events
# ============================================================================

@dataclass(frozen=True, slots=True, kw_only=True)
class SearchPerformedEvent(BaseEvent):
    """Fired when a search is performed."""

    EVENT_TYPE: str = field(init=False, repr=False, default="exegesis.search.performed")

    query: str
    user_id: str | None = None
    result_count: int = 0
    search_type: str = "hybrid"  # hybrid, semantic, keyword
    duration_ms: float | None = None
    filters: Mapping[str, Any] | None = None


# ============================================================================
# Research Events
# ============================================================================

@dataclass(frozen=True, slots=True, kw_only=True)
class HypothesisCreatedEvent(BaseEvent):
    """Fired when a research hypothesis is created."""

    EVENT_TYPE: str = field(init=False, repr=False, default="exegesis.research.hypothesis_created")

    hypothesis_id: str | UUID
    title: str
    user_id: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ResearchNoteAddedEvent(BaseEvent):
    """Fired when a research note is added."""

    EVENT_TYPE: str = field(init=False, repr=False, default="exegesis.research.note_added")

    note_id: str | UUID
    hypothesis_id: str | UUID | None = None
    user_id: str | None = None


# ============================================================================
# Export all event types
# ============================================================================

__all__ = [
    "BaseEvent",
    "DiscoveryRefreshedEvent",
    "HypothesisCreatedEvent",
    "IngestionCompletedEvent",
    "IngestionFailedEvent",
    "ResearchNoteAddedEvent",
    "SearchPerformedEvent",
    "TopicDigestGeneratedEvent",
]
