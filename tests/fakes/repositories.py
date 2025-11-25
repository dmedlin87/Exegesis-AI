"""Recording repository fakes implementing domain Protocols.

These fakes provide a structured way to verify service-repository interactions
without coupling tests to concrete persistence implementations.

Usage:
    from tests.fakes import RecordingNotesRepository
    from tests.factories.builders import build_research_note

    def test_service_creates_note():
        repo = RecordingNotesRepository()
        repo.create_return = build_research_note(note_id="created-1")

        service = ResearchService(repo)
        result = service.create_note(draft)

        assert result == repo.create_return
        assert repo.create_calls == [(draft, True)]
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from exegesis.domain import (
        Hypothesis,
        HypothesisDraft,
        ResearchNote,
        ResearchNoteDraft,
        ResearchNoteEvidenceDraft,
    )


@dataclass
class ListForOsisCall:
    """Recorded call to ResearchNoteRepository.list_for_osis."""

    osis: str
    stance: str | None = None
    claim_type: str | None = None
    tag: str | None = None
    min_confidence: float | None = None


@dataclass
class CreateNoteCall:
    """Recorded call to ResearchNoteRepository.create."""

    draft: "ResearchNoteDraft"
    commit: bool = True


@dataclass
class UpdateNoteCall:
    """Recorded call to ResearchNoteRepository.update."""

    note_id: str
    changes: dict[str, object]
    evidences: tuple["ResearchNoteEvidenceDraft", ...] | None = None


@dataclass
class ListHypothesisCall:
    """Recorded call to HypothesisRepository.list."""

    statuses: tuple[str, ...] | None = None
    min_confidence: float | None = None
    query: str | None = None


@dataclass
class UpdateHypothesisCall:
    """Recorded call to HypothesisRepository.update."""

    hypothesis_id: str
    changes: dict[str, object]


class RecordingNotesRepository:
    """Repository fake implementing ResearchNoteRepository Protocol.

    Records all method calls and returns pre-configured results.
    Implements the Protocol contract from exegesis.domain.repositories.research_notes.

    Attributes:
        list_calls: Recorded list_for_osis invocations.
        create_calls: Recorded create invocations.
        preview_calls: Recorded preview invocations.
        update_calls: Recorded update invocations.
        delete_calls: List of note_ids passed to delete.
        list_return: Value returned by list_for_osis (default: empty list).
        create_return: Value returned by create (must be set before calling).
        preview_return: Value returned by preview (must be set before calling).
        update_return: Value returned by update (must be set before calling).
    """

    def __init__(self) -> None:
        self.list_calls: list[ListForOsisCall] = []
        self.create_calls: list[CreateNoteCall] = []
        self.preview_calls: list["ResearchNoteDraft"] = []
        self.update_calls: list[UpdateNoteCall] = []
        self.delete_calls: list[str] = []

        self.list_return: list["ResearchNote"] = []
        self.create_return: "ResearchNote | None" = None
        self.preview_return: "ResearchNote | None" = None
        self.update_return: "ResearchNote | None" = None

    def list_for_osis(
        self,
        osis: str,
        *,
        stance: str | None = None,
        claim_type: str | None = None,
        tag: str | None = None,
        min_confidence: float | None = None,
    ) -> list["ResearchNote"]:
        """Record the call and return configured list."""
        self.list_calls.append(
            ListForOsisCall(
                osis=osis,
                stance=stance,
                claim_type=claim_type,
                tag=tag,
                min_confidence=min_confidence,
            )
        )
        return list(self.list_return)

    def create(
        self,
        draft: "ResearchNoteDraft",
        *,
        commit: bool = True,
    ) -> "ResearchNote":
        """Record the call and return configured result."""
        if self.create_return is None:
            raise AssertionError(
                "RecordingNotesRepository.create_return must be set before calling create()"
            )
        self.create_calls.append(CreateNoteCall(draft=draft, commit=commit))
        return self.create_return

    def preview(self, draft: "ResearchNoteDraft") -> "ResearchNote":
        """Record the call and return configured result."""
        if self.preview_return is None:
            raise AssertionError(
                "RecordingNotesRepository.preview_return must be set before calling preview()"
            )
        self.preview_calls.append(draft)
        return self.preview_return

    def update(
        self,
        note_id: str,
        changes: Mapping[str, object],
        *,
        evidences: Sequence["ResearchNoteEvidenceDraft"] | None = None,
    ) -> "ResearchNote":
        """Record the call and return configured result."""
        if self.update_return is None:
            raise AssertionError(
                "RecordingNotesRepository.update_return must be set before calling update()"
            )
        normalized_evidences = tuple(evidences) if evidences is not None else None
        self.update_calls.append(
            UpdateNoteCall(
                note_id=note_id,
                changes=dict(changes),
                evidences=normalized_evidences,
            )
        )
        return self.update_return

    def delete(self, note_id: str) -> None:
        """Record the deletion call."""
        self.delete_calls.append(note_id)

    # -------------------------------------------------------------------------
    # Assertion helpers
    # -------------------------------------------------------------------------

    def assert_no_calls(self) -> None:
        """Assert no repository methods were called."""
        assert not self.list_calls, f"Expected no list calls, got {self.list_calls}"
        assert not self.create_calls, f"Expected no create calls, got {self.create_calls}"
        assert not self.preview_calls, f"Expected no preview calls, got {self.preview_calls}"
        assert not self.update_calls, f"Expected no update calls, got {self.update_calls}"
        assert not self.delete_calls, f"Expected no delete calls, got {self.delete_calls}"

    def assert_created_once(self, *, draft: "ResearchNoteDraft | None" = None) -> None:
        """Assert create was called exactly once, optionally checking the draft."""
        assert len(self.create_calls) == 1, f"Expected 1 create call, got {len(self.create_calls)}"
        if draft is not None:
            assert self.create_calls[0].draft == draft

    def assert_deleted(self, note_id: str) -> None:
        """Assert delete was called with the specified note_id."""
        assert note_id in self.delete_calls, f"Expected delete({note_id!r}), got {self.delete_calls}"


class RecordingHypothesisRepository:
    """Repository fake implementing HypothesisRepository Protocol.

    Records all method calls and returns pre-configured results.
    Implements the Protocol contract from exegesis.domain.repositories.hypotheses.

    Attributes:
        list_calls: Recorded list invocations.
        create_calls: List of HypothesisDraft objects passed to create.
        update_calls: Recorded update invocations.
        list_return: Value returned by list (default: empty list).
        create_return: Value returned by create (must be set before calling).
        update_return: Value returned by update (must be set before calling).
    """

    def __init__(self) -> None:
        self.list_calls: list[ListHypothesisCall] = []
        self.create_calls: list["HypothesisDraft"] = []
        self.update_calls: list[UpdateHypothesisCall] = []

        self.list_return: list["Hypothesis"] = []
        self.create_return: "Hypothesis | None" = None
        self.update_return: "Hypothesis | None" = None

    def list(
        self,
        *,
        statuses: tuple[str, ...] | None = None,
        min_confidence: float | None = None,
        query: str | None = None,
    ) -> list["Hypothesis"]:
        """Record the call and return configured list."""
        self.list_calls.append(
            ListHypothesisCall(
                statuses=statuses,
                min_confidence=min_confidence,
                query=query,
            )
        )
        return list(self.list_return)

    def create(self, draft: "HypothesisDraft", *, commit: bool = True) -> "Hypothesis":
        """Record the call and return configured result."""
        if self.create_return is None:
            raise AssertionError(
                "RecordingHypothesisRepository.create_return must be set before calling create()"
            )
        self.create_calls.append(draft)
        return self.create_return

    def update(
        self,
        hypothesis_id: str,
        changes: Mapping[str, object],
    ) -> "Hypothesis":
        """Record the call and return configured result."""
        if self.update_return is None:
            raise AssertionError(
                "RecordingHypothesisRepository.update_return must be set before calling update()"
            )
        self.update_calls.append(
            UpdateHypothesisCall(hypothesis_id=hypothesis_id, changes=dict(changes))
        )
        return self.update_return

    # -------------------------------------------------------------------------
    # Assertion helpers
    # -------------------------------------------------------------------------

    def assert_no_calls(self) -> None:
        """Assert no repository methods were called."""
        assert not self.list_calls, f"Expected no list calls, got {self.list_calls}"
        assert not self.create_calls, f"Expected no create calls, got {self.create_calls}"
        assert not self.update_calls, f"Expected no update calls, got {self.update_calls}"

    def assert_created_once(self, *, draft: "HypothesisDraft | None" = None) -> None:
        """Assert create was called exactly once, optionally checking the draft."""
        assert len(self.create_calls) == 1, f"Expected 1 create call, got {len(self.create_calls)}"
        if draft is not None:
            assert self.create_calls[0] == draft

    def assert_listed_with(
        self,
        *,
        statuses: tuple[str, ...] | None = None,
        min_confidence: float | None = None,
        query: str | None = None,
    ) -> None:
        """Assert list was called with the specified filters."""
        expected = ListHypothesisCall(
            statuses=statuses,
            min_confidence=min_confidence,
            query=query,
        )
        assert expected in self.list_calls, f"Expected {expected} in {self.list_calls}"


__all__ = [
    "RecordingNotesRepository",
    "RecordingHypothesisRepository",
    "ListForOsisCall",
    "CreateNoteCall",
    "UpdateNoteCall",
    "ListHypothesisCall",
    "UpdateHypothesisCall",
]
