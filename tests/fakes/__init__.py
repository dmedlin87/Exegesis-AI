"""Reusable test fakes implementing domain repository Protocols.

This module provides recording fakes that:
1. Implement the Protocol interface from theo.domain.repositories
2. Record all calls for assertion in tests
3. Support configurable return values

These fakes formalize interface-based testing and prevent tests from
coupling to concrete repository implementations.
"""

from .repositories import (
    RecordingHypothesisRepository,
    RecordingNotesRepository,
)

__all__ = [
    "RecordingHypothesisRepository",
    "RecordingNotesRepository",
]
