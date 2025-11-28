"""Persistence models for the Evidence Dossier feature."""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, Float, Index, JSON, String, Text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from exegesis.adapters.persistence.models import Base

_JSONB = postgresql.JSONB(astext_type=Text()).with_variant(JSON, "sqlite")


class EvidenceDossier(Base):
    """Structured dossier tied to a verse and theological claim."""

    __tablename__ = "evidence_dossiers"
    __table_args__ = (
        Index("ix_evidence_dossiers_verse_ref", "verse_ref"),
        {"extend_existing": True},
    )

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    verse_ref: Mapped[str] = mapped_column(String, nullable=False, index=True)
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    textual_analysis: Mapped[dict[str, object]] = mapped_column(
        _JSONB, nullable=False, default=dict
    )
    logical_analysis: Mapped[dict[str, object]] = mapped_column(
        _JSONB, nullable=False, default=dict
    )
    scientific_analysis: Mapped[dict[str, object]] = mapped_column(
        _JSONB, nullable=False, default=dict
    )
    cultural_analysis: Mapped[dict[str, object]] = mapped_column(
        _JSONB, nullable=False, default=dict
    )

    primary_sources: Mapped[list[dict[str, object]]] = mapped_column(
        _JSONB, nullable=False, default=list
    )
    secondary_sources: Mapped[list[dict[str, object]]] = mapped_column(
        _JSONB, nullable=False, default=list
    )
    tertiary_sources: Mapped[list[dict[str, object]]] = mapped_column(
        _JSONB, nullable=False, default=list
    )

    competing_hypotheses: Mapped[list[dict[str, object]]] = mapped_column(
        _JSONB, nullable=False, default=list
    )

    meta: Mapped[dict[str, object] | None] = mapped_column(
        _JSONB, nullable=True
    )


__all__ = ["EvidenceDossier"]
