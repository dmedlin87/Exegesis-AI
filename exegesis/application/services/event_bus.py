"""Centralized event bus for domain event publishing.

This module provides a single point of access for publishing domain events,
ensuring consistent event handling across the application.

The event bus:
- Accepts typed domain events from exegesis.domain.events
- Validates events before publishing
- Routes events to configured publishers
- Provides hooks for event logging and monitoring

Usage:
    from exegesis.application.services.event_bus import event_bus
    from exegesis.domain.events import IngestionCompletedEvent

    # Publish a typed event
    event_bus.publish(IngestionCompletedEvent(
        document_id="doc-123",
        source_url="https://example.com/doc.pdf",
    ))

    # Or publish multiple events
    event_bus.publish_all([event1, event2, event3])
"""

from __future__ import annotations

import logging
from typing import Callable, Sequence

from exegesis.application.ports.events import DomainEvent, EventPublisher, NullEventPublisher
from exegesis.domain.events import BaseEvent

logger = logging.getLogger(__name__)


class EventBus:
    """Centralized event bus for publishing domain events.

    The event bus provides a single point of access for event publishing,
    with support for:
    - Typed event validation
    - Pre/post publish hooks
    - Logging and monitoring
    - Error handling
    """

    def __init__(self, publisher: EventPublisher | None = None) -> None:
        """Initialize the event bus.

        Args:
            publisher: The underlying event publisher. If None, uses NullEventPublisher.
        """
        self._publisher: EventPublisher = publisher or NullEventPublisher()
        self._pre_publish_hooks: list[Callable[[DomainEvent], None]] = []
        self._post_publish_hooks: list[Callable[[DomainEvent], None]] = []

    def configure(self, publisher: EventPublisher) -> None:
        """Configure the event publisher.

        This should be called during application startup to wire up
        the actual event infrastructure (Kafka, Redis, etc.).
        """
        self._publisher = publisher
        logger.info("Event bus configured with publisher: %s", type(publisher).__name__)

    def add_pre_publish_hook(self, hook: Callable[[DomainEvent], None]) -> None:
        """Add a hook to be called before each event is published.

        Useful for logging, metrics, or validation.
        """
        self._pre_publish_hooks.append(hook)

    def add_post_publish_hook(self, hook: Callable[[DomainEvent], None]) -> None:
        """Add a hook to be called after each event is published.

        Useful for audit logging or triggering side effects.
        """
        self._post_publish_hooks.append(hook)

    def publish(self, event: BaseEvent | DomainEvent) -> None:
        """Publish a single domain event.

        Accepts either a typed BaseEvent subclass or a raw DomainEvent.
        Typed events are automatically converted to DomainEvent format.

        Args:
            event: The event to publish

        Raises:
            EventDispatchError: If publishing fails
        """
        # Convert typed events to DomainEvent envelope
        if isinstance(event, BaseEvent):
            domain_event = event.to_domain_event()
        else:
            domain_event = event

        # Run pre-publish hooks
        for hook in self._pre_publish_hooks:
            try:
                hook(domain_event)
            except Exception:
                logger.exception("Pre-publish hook failed for event %s", domain_event.type)

        # Log the event
        logger.debug(
            "Publishing event: type=%s, key=%s",
            domain_event.type,
            domain_event.key,
        )

        # Publish via configured publisher
        self._publisher.publish(domain_event)

        # Run post-publish hooks
        for hook in self._post_publish_hooks:
            try:
                hook(domain_event)
            except Exception:
                logger.exception("Post-publish hook failed for event %s", domain_event.type)

    def publish_all(self, events: Sequence[BaseEvent | DomainEvent]) -> None:
        """Publish multiple events in sequence.

        Each event is published independently. If one fails, subsequent
        events are still attempted.

        Args:
            events: Sequence of events to publish
        """
        for event in events:
            try:
                self.publish(event)
            except Exception:
                logger.exception(
                    "Failed to publish event: %s",
                    getattr(event, "EVENT_TYPE", None) or getattr(event, "type", "unknown"),
                )


# Global event bus instance
# Configure during application startup via event_bus.configure(publisher)
event_bus = EventBus()


def get_event_bus() -> EventBus:
    """Return the global event bus instance.

    This function is provided for dependency injection scenarios
    where a callable is preferred over direct module access.
    """
    return event_bus


def configure_event_bus(publisher: EventPublisher) -> None:
    """Configure the global event bus with a publisher.

    This should be called during application startup.
    """
    event_bus.configure(publisher)


__all__ = [
    "EventBus",
    "configure_event_bus",
    "event_bus",
    "get_event_bus",
]
