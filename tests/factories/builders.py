"""Typed test data builders with caching for fast, validated test data creation.

This module replaces untyped dict payloads with domain model construction,
preserving the warm-cache speed benefit while regaining Pydantic/dataclass
validation at builder invocation time.
"""

from __future__ import annotations

import copy
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, ClassVar, ParamSpec, TypeVar

if TYPE_CHECKING:
    from pydantic import BaseModel

T = TypeVar("T")
P = ParamSpec("P")


class _BuilderCache:
    """Thread-local cache for built domain objects."""

    _cache: ClassVar[dict[str, Any]] = {}

    @classmethod
    def get(cls, key: str) -> Any | None:
        return cls._cache.get(key)

    @classmethod
    def set(cls, key: str, value: Any) -> None:
        cls._cache[key] = value

    @classmethod
    def clear(cls) -> None:
        cls._cache.clear()

    @classmethod
    def build_key(cls, name: str, kwargs: dict[str, Any]) -> str:
        """Build a deterministic cache key from builder name and arguments."""
        normalised = tuple(sorted((k, repr(v)) for k, v in kwargs.items()))
        return f"{name}:{normalised}"


def _clone_instance(obj: T) -> T:
    """Deep clone a dataclass or Pydantic model instance."""
    if is_dataclass(obj) and not isinstance(obj, type):
        # Frozen dataclass: reconstruct from dict
        return obj.__class__(**copy.deepcopy(asdict(obj)))  # type: ignore[return-value]

    # Check for Pydantic model (duck-type to avoid import dependency)
    if hasattr(obj, "model_copy"):
        return obj.model_copy(deep=True)  # type: ignore[return-value,union-attr]
    if hasattr(obj, "copy"):  # Pydantic v1
        return obj.copy(deep=True)  # type: ignore[return-value,union-attr]

    # Fallback for other types
    return copy.deepcopy(obj)


def cached_builder(fn: Callable[P, T]) -> Callable[P, T]:
    """Decorator that caches builder results and returns cloned instances.

    Usage:
        @cached_builder
        def build_research_note(*, note_id: str = "note-1", ...) -> ResearchNote:
            return ResearchNote(id=note_id, ...)

    The first call with a given set of keyword arguments builds and caches
    the domain object. Subsequent calls with identical arguments return
    a deep clone of the cached instance, ensuring test isolation while
    avoiding repeated construction overhead.
    """

    @wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        # Include positional args in key for completeness
        full_kwargs = {f"_arg_{i}": v for i, v in enumerate(args)}
        full_kwargs.update(kwargs)  # type: ignore[arg-type]

        cache_key = _BuilderCache.build_key(fn.__name__, full_kwargs)
        cached = _BuilderCache.get(cache_key)
        if cached is not None:
            return _clone_instance(cached)

        result = fn(*args, **kwargs)
        _BuilderCache.set(cache_key, result)
        return _clone_instance(result)

    return wrapper


# ---------------------------------------------------------------------------
# Domain Model Builders
# ---------------------------------------------------------------------------

from exegesis.domain import (
    Hypothesis,
    HypothesisDraft,
    ResearchNote,
    ResearchNoteDraft,
    ResearchNoteEvidence,
    ResearchNoteEvidenceDraft,
    VariantEntry,
)


@cached_builder
def build_research_note(
    *,
    note_id: str = "note-1",
    osis: str = "John.3.16",
    body: str = "For God so loved the world.",
    title: str | None = "Famous verse",
    stance: str | None = "affirming",
    claim_type: str | None = "theology",
    confidence: float | None = 0.9,
    tags: tuple[str, ...] | None = None,
    evidences: tuple[ResearchNoteEvidence, ...] = (),
    request_id: str | None = None,
    created_by: str | None = None,
    tenant_id: str | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> ResearchNote:
    """Build a ResearchNote domain entity with sensible defaults."""
    return ResearchNote(
        id=note_id,
        osis=osis,
        body=body,
        title=title,
        stance=stance,
        claim_type=claim_type,
        confidence=confidence,
        tags=tags,
        evidences=evidences,
        request_id=request_id,
        created_by=created_by,
        tenant_id=tenant_id,
        created_at=created_at,
        updated_at=updated_at,
    )


@cached_builder
def build_research_note_draft(
    *,
    osis: str = "John.3.16",
    body: str = "Some commentary",
    title: str | None = None,
    stance: str | None = None,
    claim_type: str | None = None,
    confidence: float | None = None,
    tags: tuple[str, ...] | None = None,
    evidences: tuple[ResearchNoteEvidenceDraft, ...] = (),
    request_id: str | None = None,
    end_user_id: str | None = None,
    tenant_id: str | None = None,
) -> ResearchNoteDraft:
    """Build a ResearchNoteDraft command payload."""
    return ResearchNoteDraft(
        osis=osis,
        body=body,
        title=title,
        stance=stance,
        claim_type=claim_type,
        confidence=confidence,
        tags=tags,
        evidences=evidences,
        request_id=request_id,
        end_user_id=end_user_id,
        tenant_id=tenant_id,
    )


@cached_builder
def build_research_note_evidence(
    *,
    evidence_id: str | None = "ev-1",
    source_type: str | None = "scripture",
    source_ref: str | None = None,
    osis_refs: tuple[str, ...] | None = None,
    citation: str | None = "John 3:16",
    snippet: str | None = "For God so loved...",
    meta: dict[str, object] | None = None,
) -> ResearchNoteEvidence:
    """Build a ResearchNoteEvidence value object."""
    return ResearchNoteEvidence(
        id=evidence_id,
        source_type=source_type,
        source_ref=source_ref,
        osis_refs=osis_refs,
        citation=citation,
        snippet=snippet,
        meta=meta,
    )


@cached_builder
def build_research_note_evidence_draft(
    *,
    source_type: str | None = None,
    source_ref: str | None = None,
    osis_refs: tuple[str, ...] | None = None,
    citation: str | None = "John 3:16",
    snippet: str | None = "Snippet",
    meta: dict[str, object] | None = None,
) -> ResearchNoteEvidenceDraft:
    """Build a ResearchNoteEvidenceDraft for note creation."""
    return ResearchNoteEvidenceDraft(
        source_type=source_type,
        source_ref=source_ref,
        osis_refs=osis_refs,
        citation=citation,
        snippet=snippet,
        meta=meta,
    )


@cached_builder
def build_hypothesis(
    *,
    hypothesis_id: str = "hypo-1",
    claim: str = "Claim text",
    confidence: float = 0.5,
    status: str = "active",
    trail_id: str | None = None,
    supporting_passage_ids: tuple[str, ...] | None = None,
    contradicting_passage_ids: tuple[str, ...] | None = None,
    perspective_scores: dict[str, float] | None = None,
    metadata: dict[str, object] | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> Hypothesis:
    """Build a Hypothesis domain entity."""
    return Hypothesis(
        id=hypothesis_id,
        claim=claim,
        confidence=confidence,
        status=status,
        trail_id=trail_id,
        supporting_passage_ids=supporting_passage_ids,
        contradicting_passage_ids=contradicting_passage_ids,
        perspective_scores=perspective_scores,
        metadata=metadata,
        created_at=created_at,
        updated_at=updated_at,
    )


@cached_builder
def build_hypothesis_draft(
    *,
    claim: str = "Hypothesis claim",
    confidence: float = 0.6,
    status: str = "active",
    trail_id: str | None = None,
    supporting_passage_ids: tuple[str, ...] | None = None,
    contradicting_passage_ids: tuple[str, ...] | None = None,
    perspective_scores: dict[str, float] | None = None,
    metadata: dict[str, object] | None = None,
) -> HypothesisDraft:
    """Build a HypothesisDraft command payload."""
    return HypothesisDraft(
        claim=claim,
        confidence=confidence,
        status=status,
        trail_id=trail_id,
        supporting_passage_ids=supporting_passage_ids,
        contradicting_passage_ids=contradicting_passage_ids,
        perspective_scores=perspective_scores,
        metadata=metadata,
    )


@cached_builder
def build_variant_entry(
    *,
    variant_id: str = "var-1",
    osis: str = "John.3.16",
    category: str = "manuscript",
    reading: str = "Reading",
    note: str | None = None,
    source: str | None = None,
    witness: str | None = None,
    translation: str | None = None,
    confidence: float | None = None,
    dataset: str | None = None,
    disputed: bool | None = None,
    witness_metadata: dict[str, object] | None = None,
) -> VariantEntry:
    """Build a VariantEntry for textual criticism tests."""
    return VariantEntry(
        id=variant_id,
        osis=osis,
        category=category,
        reading=reading,
        note=note,
        source=source,
        witness=witness,
        translation=translation,
        confidence=confidence,
        dataset=dataset,
        disputed=disputed,
        witness_metadata=witness_metadata,
    )


# ---------------------------------------------------------------------------
# Verse/Scripture Data Builders (typed alternative to dict payloads)
# ---------------------------------------------------------------------------

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VerseData:
    """Typed representation of verse test data."""

    book: str
    chapter: int
    verses: tuple["SingleVerse", ...]


@dataclass(frozen=True, slots=True)
class SingleVerse:
    """Individual verse within VerseData."""

    number: int
    text: str


@dataclass(frozen=True, slots=True)
class UserData:
    """Typed representation of user test data."""

    name: str
    email: str
    preferences: "UserPreferences"


@dataclass(frozen=True, slots=True)
class UserPreferences:
    """User preference settings."""

    newsletter: bool = False
    beta_opt_in: bool = True


@cached_builder
def build_verse_data(
    *,
    book: str = "Genesis",
    chapter: int = 1,
    verses: int = 5,
) -> VerseData:
    """Build typed verse data with validation."""
    verse_items = tuple(
        SingleVerse(
            number=i + 1,
            text=f"Sample verse {i + 1} from {book} {chapter}",
        )
        for i in range(verses)
    )
    return VerseData(book=book, chapter=chapter, verses=verse_items)


@cached_builder
def build_user_data(
    *,
    name: str = "Test User",
    email: str = "user@example.com",
    newsletter: bool = False,
    beta_opt_in: bool = True,
) -> UserData:
    """Build typed user data with validation."""
    return UserData(
        name=name,
        email=email,
        preferences=UserPreferences(newsletter=newsletter, beta_opt_in=beta_opt_in),
    )


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    # Cache management
    "cached_builder",
    "_BuilderCache",
    # Research domain builders
    "build_research_note",
    "build_research_note_draft",
    "build_research_note_evidence",
    "build_research_note_evidence_draft",
    "build_hypothesis",
    "build_hypothesis_draft",
    "build_variant_entry",
    # Generic data builders
    "build_verse_data",
    "build_user_data",
    # Typed data models
    "VerseData",
    "SingleVerse",
    "UserData",
    "UserPreferences",
]
