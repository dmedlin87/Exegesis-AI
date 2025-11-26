"""Tests for typed domain events."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from exegesis.domain.events import (
    BaseEvent,
    DiscoveryRefreshedEvent,
    IngestionCompletedEvent,
    IngestionFailedEvent,
    SearchPerformedEvent,
    TopicDigestGeneratedEvent,
)


class TestBaseEvent:
    """Tests for BaseEvent base class."""

    def test_to_domain_event_creates_envelope(self):
        """BaseEvent.to_domain_event creates proper envelope."""
        # Use a concrete event type since BaseEvent's EVENT_TYPE uses field(init=False)
        event = IngestionCompletedEvent(document_id="test-doc")
        domain_event = event.to_domain_event()

        assert domain_event.type == "exegesis.ingestion.completed"
        assert domain_event.payload["document_id"] == "test-doc"
        assert domain_event.occurred_at is not None


class TestIngestionEvents:
    """Tests for ingestion-related events."""

    def test_ingestion_completed_minimal(self):
        """IngestionCompletedEvent with minimal fields."""
        event = IngestionCompletedEvent(document_id="doc-123")

        assert event.document_id == "doc-123"
        assert event.EVENT_TYPE == "exegesis.ingestion.completed"

        payload = event.to_payload()
        assert payload["document_id"] == "doc-123"
        assert "source_url" not in payload  # Optional fields excluded when None

    def test_ingestion_completed_full(self):
        """IngestionCompletedEvent with all fields."""
        doc_id = uuid4()
        event = IngestionCompletedEvent(
            document_id=doc_id,
            source_url="https://example.com/doc.pdf",
            document_type="pdf",
            title="Test Document",
            page_count=10,
            passage_count=50,
            frontmatter={"author": "Test Author"},
        )

        payload = event.to_payload()
        assert payload["document_id"] == str(doc_id)
        assert payload["source_url"] == "https://example.com/doc.pdf"
        assert payload["document_type"] == "pdf"
        assert payload["title"] == "Test Document"
        assert payload["page_count"] == 10
        assert payload["passage_count"] == 50
        assert payload["frontmatter"]["author"] == "Test Author"

    def test_ingestion_completed_to_domain_event(self):
        """IngestionCompletedEvent converts to DomainEvent properly."""
        event = IngestionCompletedEvent(
            document_id="doc-456",
            title="My Doc",
        )

        domain_event = event.to_domain_event()
        assert domain_event.type == "exegesis.ingestion.completed"
        assert domain_event.payload["document_id"] == "doc-456"
        assert domain_event.payload["title"] == "My Doc"

    def test_ingestion_failed_event(self):
        """IngestionFailedEvent captures error details."""
        event = IngestionFailedEvent(
            source_url="https://example.com/bad.pdf",
            error_code="PARSE_ERROR",
            error_message="Failed to parse PDF",
        )

        assert event.EVENT_TYPE == "exegesis.ingestion.failed"
        payload = event.to_payload()
        assert payload["source_url"] == "https://example.com/bad.pdf"
        assert payload["error_code"] == "PARSE_ERROR"


class TestDiscoveryEvents:
    """Tests for discovery-related events."""

    def test_discovery_refreshed_event(self):
        """DiscoveryRefreshedEvent captures refresh metrics."""
        event = DiscoveryRefreshedEvent(
            user_id="user-123",
            discovery_count=15,
            duration_ms=250.5,
        )

        assert event.EVENT_TYPE == "exegesis.discoveries.refreshed"
        payload = event.to_payload()
        assert payload["user_id"] == "user-123"
        assert payload["discovery_count"] == 15
        assert payload["duration_ms"] == 250.5


class TestTopicDigestEvents:
    """Tests for topic digest events."""

    def test_topic_digest_generated_event(self):
        """TopicDigestGeneratedEvent captures digest info."""
        event = TopicDigestGeneratedEvent(
            digest_id="digest-789",
            topic_count=5,
            document_count=20,
        )

        assert event.EVENT_TYPE == "exegesis.topic_digest.generated"
        payload = event.to_payload()
        assert payload["digest_id"] == "digest-789"
        assert payload["topic_count"] == 5


class TestSearchEvents:
    """Tests for search-related events."""

    def test_search_performed_event(self):
        """SearchPerformedEvent captures search metrics."""
        event = SearchPerformedEvent(
            query="what is the meaning of life",
            user_id="user-456",
            result_count=10,
            search_type="semantic",
            duration_ms=150.0,
            filters={"collection": "philosophy"},
        )

        assert event.EVENT_TYPE == "exegesis.search.performed"
        payload = event.to_payload()
        assert payload["query"] == "what is the meaning of life"
        assert payload["result_count"] == 10
        assert payload["search_type"] == "semantic"
        assert payload["filters"]["collection"] == "philosophy"


class TestEventImmutability:
    """Tests ensuring events are immutable."""

    def test_events_are_frozen(self):
        """Typed events cannot be modified after creation."""
        event = IngestionCompletedEvent(document_id="doc-123")

        with pytest.raises(AttributeError):
            event.document_id = "different-id"  # type: ignore[misc]
