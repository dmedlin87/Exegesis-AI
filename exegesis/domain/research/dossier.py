"""Evidence Dossier domain models for theological research."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from .entities import Hypothesis

OSISReference = str


@dataclass(frozen=True, slots=True)
class TextualAnalysis:
    """Textual-critical lens observations for a claim."""

    summary: str | None = None
    manuscript_support: tuple[str, ...] = ()
    variant_observations: tuple[str, ...] = ()
    patristic_citations: tuple[str, ...] = ()
    verdict: str | None = None
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class LogicalAnalysis:
    """Logical coherence and argumentative structure."""

    premises: tuple[str, ...] = ()
    inferences: tuple[str, ...] = ()
    counterarguments: tuple[str, ...] = ()
    fallacies: tuple[str, ...] = ()
    verdict: str | None = None
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class ScientificAnalysis:
    """Scientific, historical, or empirical evaluation."""

    observations: tuple[str, ...] = ()
    methodologies: tuple[str, ...] = ()
    compatibility_notes: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    verdict: str | None = None
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class CulturalAnalysis:
    """Cultural, reception, or sociological perspective."""

    contexts: tuple[str, ...] = ()
    reception_history: tuple[str, ...] = ()
    liturgical_usage: tuple[str, ...] = ()
    social_implications: tuple[str, ...] = ()
    verdict: str | None = None
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class EvidenceDossier:
    """Complete dossier answer anchored to a verse and claim."""

    verse_ref: OSISReference
    claim: str
    confidence_score: float
    created_at: datetime
    textual_analysis: TextualAnalysis
    logical_analysis: LogicalAnalysis
    scientific_analysis: ScientificAnalysis
    cultural_analysis: CulturalAnalysis
    primary_sources: tuple[str, ...] = ()
    secondary_sources: tuple[str, ...] = ()
    tertiary_sources: tuple[str, ...] = ()
    competing_hypotheses: tuple[Hypothesis, ...] = ()
    metadata: Mapping[str, object] | None = None
    last_updated: datetime | None = None


__all__ = [
    "CulturalAnalysis",
    "EvidenceDossier",
    "LogicalAnalysis",
    "ScientificAnalysis",
    "TextualAnalysis",
    "OSISReference",
]
