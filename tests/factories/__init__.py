"""Test factory utilities for building domain objects and test data.

This package provides:
- **application.py**: Context-managed app container factory for test isolation
- **optimized.py**: Legacy dict-based cached test data (deprecated, use builders)
- **builders.py**: Typed builders with caching for domain model construction

Preferred usage:
    from tests.factories.builders import build_research_note, build_hypothesis
    from tests.factories.application import isolated_application_container
"""

from .application import isolated_application_container
from .builders import (
    build_hypothesis,
    build_hypothesis_draft,
    build_research_note,
    build_research_note_draft,
    build_research_note_evidence,
    build_research_note_evidence_draft,
    build_user_data,
    build_variant_entry,
    build_verse_data,
    cached_builder,
)

__all__ = [
    # Application isolation
    "isolated_application_container",
    # Domain builders
    "build_hypothesis",
    "build_hypothesis_draft",
    "build_research_note",
    "build_research_note_draft",
    "build_research_note_evidence",
    "build_research_note_evidence_draft",
    "build_variant_entry",
    # Generic data builders
    "build_verse_data",
    "build_user_data",
    # Decorator
    "cached_builder",
]
