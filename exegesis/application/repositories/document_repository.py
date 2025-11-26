"""Repository abstraction for document persistence operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from exegesis.application.dtos import DocumentDTO, DocumentSummaryDTO
from exegesis.domain.discoveries import DocumentEmbedding


class DocumentRepository(ABC):
    """Abstract interface for document data access."""

    @abstractmethod
    def list_with_embeddings(self, user_id: str) -> list[DocumentEmbedding]:
        """Return documents with averaged passage embeddings for *user_id*."""
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, document_id: str) -> DocumentDTO | None:
        """Retrieve a single document by its identifier."""
        raise NotImplementedError

    @abstractmethod
    def list_summaries(
        self, user_id: str, limit: int | None = None
    ) -> list[DocumentSummaryDTO]:
        """Return lightweight document summaries for the supplied *user_id*."""
        raise NotImplementedError

    @abstractmethod
    def list_created_since(
        self, since: datetime, limit: int | None = None
    ) -> list[DocumentDTO]:
        """Return documents created on/after *since*, ordered chronologically."""
        raise NotImplementedError


__all__ = ["DocumentRepository"]

