"""Repository abstraction for chat session persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod

from exegesis.application.dtos import ChatSessionDTO


class ChatSessionRepository(ABC):
    """Interface describing chat session data access patterns."""

    @abstractmethod
    def list_recent(self, limit: int) -> list[ChatSessionDTO]:
        """Return the most recently updated chat sessions up to *limit*."""
        raise NotImplementedError


__all__ = ["ChatSessionRepository"]

