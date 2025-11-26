"""Tests for the centralized event bus."""

from __future__ import annotations

from typing import Any

import pytest

from exegesis.application.ports.events import DomainEvent, EventPublisher
from exegesis.application.services.event_bus import EventBus, configure_event_bus, event_bus
from exegesis.domain.events import IngestionCompletedEvent


class MockPublisher(EventPublisher):
    """Mock publisher for testing."""

    def __init__(self) -> None:
        self.published: list[DomainEvent] = []

    def publish(self, event: DomainEvent) -> None:
        self.published.append(event)


class FailingPublisher(EventPublisher):
    """Publisher that always fails."""

    def publish(self, event: DomainEvent) -> None:
        raise RuntimeError("Publisher failed")


class TestEventBus:
    """Tests for EventBus class."""

    def test_publish_typed_event(self):
        """EventBus publishes typed events correctly."""
        publisher = MockPublisher()
        bus = EventBus(publisher)

        event = IngestionCompletedEvent(
            document_id="doc-123",
            title="Test Doc",
        )

        bus.publish(event)

        assert len(publisher.published) == 1
        published = publisher.published[0]
        assert published.type == "exegesis.ingestion.completed"
        assert published.payload["document_id"] == "doc-123"
        assert published.payload["title"] == "Test Doc"

    def test_publish_raw_domain_event(self):
        """EventBus publishes raw DomainEvent objects."""
        publisher = MockPublisher()
        bus = EventBus(publisher)

        event = DomainEvent(
            type="test.event",
            payload={"data": "value"},
        )

        bus.publish(event)

        assert len(publisher.published) == 1
        assert publisher.published[0].type == "test.event"

    def test_publish_all_multiple_events(self):
        """EventBus.publish_all handles multiple events."""
        publisher = MockPublisher()
        bus = EventBus(publisher)

        events = [
            IngestionCompletedEvent(document_id="doc-1"),
            IngestionCompletedEvent(document_id="doc-2"),
            IngestionCompletedEvent(document_id="doc-3"),
        ]

        bus.publish_all(events)

        assert len(publisher.published) == 3
        assert publisher.published[0].payload["document_id"] == "doc-1"
        assert publisher.published[2].payload["document_id"] == "doc-3"

    def test_configure_changes_publisher(self):
        """EventBus.configure replaces the publisher."""
        initial_publisher = MockPublisher()
        new_publisher = MockPublisher()
        bus = EventBus(initial_publisher)

        bus.configure(new_publisher)

        event = IngestionCompletedEvent(document_id="doc-123")
        bus.publish(event)

        assert len(initial_publisher.published) == 0
        assert len(new_publisher.published) == 1

    def test_pre_publish_hook_called(self):
        """Pre-publish hooks are called before publishing."""
        publisher = MockPublisher()
        bus = EventBus(publisher)

        hook_calls: list[DomainEvent] = []
        bus.add_pre_publish_hook(lambda e: hook_calls.append(e))

        event = IngestionCompletedEvent(document_id="doc-123")
        bus.publish(event)

        assert len(hook_calls) == 1
        assert hook_calls[0].type == "exegesis.ingestion.completed"

    def test_post_publish_hook_called(self):
        """Post-publish hooks are called after publishing."""
        publisher = MockPublisher()
        bus = EventBus(publisher)

        hook_calls: list[DomainEvent] = []
        bus.add_post_publish_hook(lambda e: hook_calls.append(e))

        event = IngestionCompletedEvent(document_id="doc-123")
        bus.publish(event)

        assert len(hook_calls) == 1

    def test_hook_failure_does_not_stop_publishing(self):
        """Failing hooks don't prevent event publishing."""
        publisher = MockPublisher()
        bus = EventBus(publisher)

        def failing_hook(e: DomainEvent) -> None:
            raise ValueError("Hook failed")

        bus.add_pre_publish_hook(failing_hook)

        event = IngestionCompletedEvent(document_id="doc-123")
        bus.publish(event)  # Should not raise

        assert len(publisher.published) == 1

    def test_publish_all_continues_on_failure(self):
        """publish_all continues after individual event failures."""
        publisher = MockPublisher()
        bus = EventBus(publisher)

        # First event will fail, others should still be attempted
        call_count = {"count": 0}
        original_publish = publisher.publish

        def counting_publish(event: DomainEvent) -> None:
            call_count["count"] += 1
            if call_count["count"] == 2:
                raise RuntimeError("Simulated failure")
            original_publish(event)

        publisher.publish = counting_publish  # type: ignore[method-assign]

        events = [
            IngestionCompletedEvent(document_id="doc-1"),
            IngestionCompletedEvent(document_id="doc-2"),  # Will fail
            IngestionCompletedEvent(document_id="doc-3"),
        ]

        bus.publish_all(events)  # Should not raise

        # Events 1 and 3 should have been published
        assert len(publisher.published) == 2


class TestGlobalEventBus:
    """Tests for the global event bus instance."""

    def test_global_event_bus_exists(self):
        """Global event_bus is accessible."""
        assert event_bus is not None
        assert isinstance(event_bus, EventBus)

    def test_configure_event_bus_function(self):
        """configure_event_bus configures the global instance."""
        publisher = MockPublisher()

        # Save original publisher
        original = event_bus._publisher

        try:
            configure_event_bus(publisher)

            event = IngestionCompletedEvent(document_id="doc-123")
            event_bus.publish(event)

            assert len(publisher.published) == 1
        finally:
            # Restore original publisher
            event_bus._publisher = original
