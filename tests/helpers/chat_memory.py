"""Test helpers for chat memory workflow functions.

These helpers wrap private workflow functions from the chat module,
providing a stable test API that insulates tests from internal renames
and reduces duplication in Arrange steps.

Usage:
    from tests.helpers import make_chat_entry, prepare_memory_context

    def test_memory_ranking():
        entries = [
            make_chat_entry(question="Q1", answer="A1", topics=["hope"]),
            make_chat_entry(question="Q2", answer="A2", topics=["law"]),
        ]
        context = prepare_memory_context(entries, focus=some_focus)
        assert "Q1" in context[0].lower()
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from exegesis.infrastructure.api.app.models.ai import ChatMemoryEntry, IntentTagPayload
    from exegesis.infrastructure.api.app.research.ai.memory_metadata import MemoryFocus


def make_chat_entry(
    *,
    question: str = "Sample question?",
    answer: str = "Sample answer.",
    created_at: datetime | None = None,
    intent_tags: "list[IntentTagPayload] | None" = None,
    prompt: str | None = None,
    answer_summary: str | None = None,
    topics: list[str] | None = None,
    goal_ids: list[str] | None = None,
    entities: list[str] | None = None,
    source_types: list[str] | None = None,
    sentiment: str | None = None,
    goal_id: str | None = None,
    trail_id: str | None = None,
    embedding: list[float] | None = None,
    key_entities: list[str] | None = None,
    recommended_actions: list[str] | None = None,
    minutes_ago: int | None = None,
) -> "ChatMemoryEntry":
    """Create a ChatMemoryEntry for testing.

    Args:
        question: The user's question text.
        answer: The assistant's response text.
        created_at: When the entry was created. Defaults to now.
        intent_tags: List of intent tag payloads.
        prompt: Optional prompt text used.
        answer_summary: Summarized answer text.
        topics: Topic keywords extracted from the exchange.
        goal_ids: IDs of goals related to this entry.
        entities: Named entities mentioned.
        source_types: Types of sources cited.
        sentiment: Detected sentiment (positive/negative/neutral).
        goal_id: ID of the active goal during this exchange.
        trail_id: ID of the research trail.
        embedding: Pre-computed embedding vector.
        key_entities: Key entities for display.
        recommended_actions: Suggested follow-up actions.
        minutes_ago: Convenience param to set created_at relative to now.

    Returns:
        A ChatMemoryEntry instance for use in tests.
    """
    from exegesis.infrastructure.api.app.models.ai import ChatMemoryEntry

    if created_at is None:
        if minutes_ago is not None:
            created_at = datetime.now(UTC) - timedelta(minutes=minutes_ago)
        else:
            created_at = datetime.now(UTC)

    return ChatMemoryEntry(
        question=question,
        answer=answer,
        created_at=created_at,
        intent_tags=intent_tags,
        prompt=prompt,
        answer_summary=answer_summary,
        topics=topics,
        goal_ids=goal_ids,
        entities=entities,
        source_types=source_types,
        sentiment=sentiment,
        goal_id=goal_id,
        trail_id=trail_id,
        embedding=embedding,
        key_entities=key_entities or [],
        recommended_actions=recommended_actions or [],
    )


def make_legacy_memory_record(
    *,
    record_id: str = "legacy-record",
    question: str = "What is faith?",
    answer: str = "Faith is confidence in things hoped for.",
    created_at: datetime | None = None,
) -> SimpleNamespace:
    """Create a SimpleNamespace mimicking a legacy ChatSession record.

    This helper simulates legacy database records that store memory entries
    as raw dictionaries without full schema fields, useful for testing
    backward-compatible parsing.

    Args:
        record_id: The record ID.
        question: The question text.
        answer: The answer text.
        created_at: Timestamp for the entry. Defaults to now.

    Returns:
        A SimpleNamespace with id and memory_snippets attributes.
    """
    if created_at is None:
        created_at = datetime.now(UTC)

    legacy_entry = {
        "question": question,
        "answer": answer,
        "created_at": created_at.isoformat(),
    }
    return SimpleNamespace(id=record_id, memory_snippets=[legacy_entry])


def load_memory_entries(record: object | None) -> "list[ChatMemoryEntry]":
    """Load ChatMemoryEntry objects from a ChatSession record.

    Wraps the private `_load_memory_entries` function for test use.

    Args:
        record: A ChatSession instance or None.

    Returns:
        List of parsed ChatMemoryEntry objects, sorted by created_at.
    """
    from exegesis.infrastructure.api.app.routes.ai.workflows.chat import (
        _load_memory_entries,
    )

    return _load_memory_entries(record)


def prepare_memory_context(
    entries: "Sequence[ChatMemoryEntry]",
    *,
    query: str | None = None,
    focus: "MemoryFocus | None" = None,
) -> list[str]:
    """Prepare memory context snippets for chat completion.

    Wraps the private `_prepare_memory_context` function for test use.
    Ranks entries by relevance to the query and focus, then returns
    formatted snippet strings within the character budget.

    Args:
        entries: Memory entries to process.
        query: Optional query for embedding-based ranking.
        focus: Optional MemoryFocus for prioritizing matching entries.

    Returns:
        List of formatted memory snippet strings.
    """
    from exegesis.infrastructure.api.app.routes.ai.workflows.chat import (
        _prepare_memory_context,
    )

    return _prepare_memory_context(entries, query=query, focus=focus)


def prepare_focus_context(
    entries: "Sequence[ChatMemoryEntry]",
    *,
    question: str,
    intent_tags: "list[IntentTagPayload] | None" = None,
) -> list[str]:
    """Prepare memory context with auto-generated focus from question.

    Convenience wrapper that extracts memory metadata from the question
    and intent tags, then uses the resulting focus for context preparation.

    Args:
        entries: Memory entries to process.
        question: The current user question.
        intent_tags: Optional intent tags for focus extraction.

    Returns:
        List of formatted memory snippet strings prioritized by focus.
    """
    from exegesis.infrastructure.api.app.research.ai.memory_metadata import (
        extract_memory_metadata,
    )
    from exegesis.infrastructure.api.app.routes.ai.workflows.chat import (
        _prepare_memory_context,
    )

    metadata = extract_memory_metadata(
        question=question,
        answer=None,
        intent_tags=intent_tags,
    )
    focus = metadata.to_focus()
    return _prepare_memory_context(entries, focus=focus)


__all__ = [
    "load_memory_entries",
    "make_chat_entry",
    "make_legacy_memory_record",
    "prepare_focus_context",
    "prepare_memory_context",
]
