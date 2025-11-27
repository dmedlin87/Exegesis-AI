"""Repository abstraction for research collection persistence operations."""

from __future__ import annotations

from abc import ABC, abstractmethod

from exegesis.application.dtos.collection import (
    AddCollectionItemDTO,
    CollectionItemDTO,
    CreateCollectionDTO,
    ResearchCollectionDTO,
)


class CollectionRepository(ABC):
    """Abstract interface for research collection data access."""

    @abstractmethod
    def create(self, dto: CreateCollectionDTO) -> ResearchCollectionDTO:
        """Create a new research collection.

        Args:
            dto: Data for the new collection.

        Returns:
            The created collection with generated ID.
        """
        raise NotImplementedError

    @abstractmethod
    def get_by_id(
        self, collection_id: str, *, user_id: str | None = None
    ) -> ResearchCollectionDTO | None:
        """Retrieve a collection by its identifier.

        Args:
            collection_id: The collection's unique identifier.
            user_id: Optional user filter for authorization.

        Returns:
            The collection if found and accessible, None otherwise.
        """
        raise NotImplementedError

    @abstractmethod
    def list_all(
        self,
        user_id: str,
        *,
        include_public: bool = True,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ResearchCollectionDTO]:
        """List collections accessible to a user.

        Args:
            user_id: The user requesting collections.
            include_public: Whether to include public collections.
            limit: Maximum number of collections to return.
            offset: Number of collections to skip.

        Returns:
            List of accessible collections.
        """
        raise NotImplementedError

    @abstractmethod
    def update(
        self,
        collection_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        is_public: bool | None = None,
    ) -> ResearchCollectionDTO | None:
        """Update collection metadata.

        Args:
            collection_id: The collection to update.
            name: New name if changing.
            description: New description if changing.
            is_public: New visibility if changing.

        Returns:
            Updated collection or None if not found.
        """
        raise NotImplementedError

    @abstractmethod
    def delete(self, collection_id: str) -> bool:
        """Delete a collection and all its items.

        Args:
            collection_id: The collection to delete.

        Returns:
            True if deleted, False if not found.
        """
        raise NotImplementedError

    @abstractmethod
    def add_item(self, dto: AddCollectionItemDTO) -> CollectionItemDTO:
        """Add an item to a collection.

        Args:
            dto: Data for the new item.

        Returns:
            The created collection item.
        """
        raise NotImplementedError

    @abstractmethod
    def remove_item(self, collection_id: str, item_id: str) -> bool:
        """Remove an item from a collection.

        Args:
            collection_id: The collection containing the item.
            item_id: The item to remove.

        Returns:
            True if removed, False if not found.
        """
        raise NotImplementedError

    @abstractmethod
    def get_item(
        self, collection_id: str, item_id: str
    ) -> CollectionItemDTO | None:
        """Retrieve a specific item from a collection.

        Args:
            collection_id: The collection containing the item.
            item_id: The item identifier.

        Returns:
            The item if found, None otherwise.
        """
        raise NotImplementedError

    @abstractmethod
    def reorder_items(
        self, collection_id: str, item_ids: list[str]
    ) -> list[CollectionItemDTO]:
        """Reorder items in a collection.

        Args:
            collection_id: The collection to reorder.
            item_ids: Items in the new order.

        Returns:
            Updated list of items.
        """
        raise NotImplementedError


__all__ = ["CollectionRepository"]
