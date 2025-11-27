"""Application service orchestrating research collection workflows."""

from __future__ import annotations

from typing import TYPE_CHECKING

from exegesis.application.dtos.collection import (
    AddCollectionItemDTO,
    CollectionItemDTO,
    CollectionItemType,
    CreateCollectionDTO,
    ResearchCollectionDTO,
)
from exegesis.application.repositories.collection_repository import (
    CollectionRepository,
)

if TYPE_CHECKING:
    from exegesis.application.repositories.document_repository import (
        DocumentRepository,
    )


class CollectionNotFoundError(Exception):
    """Raised when a collection cannot be found."""

    def __init__(self, collection_id: str):
        super().__init__(f"Collection not found: {collection_id}")
        self.collection_id = collection_id


class CollectionItemNotFoundError(Exception):
    """Raised when a collection item cannot be found."""

    def __init__(self, item_id: str):
        super().__init__(f"Collection item not found: {item_id}")
        self.item_id = item_id


class ItemNotFoundError(Exception):
    """Raised when the referenced item (document, chat, etc.) does not exist."""

    def __init__(self, item_type: CollectionItemType, item_id: str):
        super().__init__(f"{item_type.value} not found: {item_id}")
        self.item_type = item_type
        self.item_id = item_id


class UnauthorizedCollectionAccessError(Exception):
    """Raised when user lacks access to a collection."""

    def __init__(self, user_id: str, collection_id: str):
        super().__init__(
            f"User {user_id} does not have access to collection {collection_id}"
        )
        self.user_id = user_id
        self.collection_id = collection_id


class CollectionService:
    """Facade aggregating research collection application logic.

    This service handles:
    - Creating and managing research collections
    - Adding/removing items with existence validation
    - Access control for collection operations
    """

    def __init__(
        self,
        collection_repository: CollectionRepository,
        *,
        document_repository: "DocumentRepository | None" = None,
    ):
        """Initialize the collection service.

        Args:
            collection_repository: Repository for collection persistence.
            document_repository: Optional repository for validating document items.
        """
        self._collection_repository = collection_repository
        self._document_repository = document_repository

    # Collection CRUD operations -----------------------------------------------

    def create_collection(
        self,
        user_id: str,
        name: str,
        *,
        description: str | None = None,
        is_public: bool = False,
    ) -> ResearchCollectionDTO:
        """Create a new research collection.

        Args:
            user_id: Owner of the collection.
            name: Display name for the collection.
            description: Optional description.
            is_public: Whether the collection is publicly visible.

        Returns:
            The newly created collection.
        """
        dto = CreateCollectionDTO(
            user_id=user_id,
            name=name,
            description=description,
            is_public=is_public,
        )
        return self._collection_repository.create(dto)

    def get_collection(
        self,
        collection_id: str,
        *,
        user_id: str | None = None,
    ) -> ResearchCollectionDTO:
        """Retrieve a collection by ID.

        Args:
            collection_id: The collection identifier.
            user_id: User requesting access (for authorization).

        Returns:
            The requested collection.

        Raises:
            CollectionNotFoundError: If collection doesn't exist or isn't accessible.
        """
        collection = self._collection_repository.get_by_id(
            collection_id, user_id=user_id
        )
        if collection is None:
            raise CollectionNotFoundError(collection_id)
        return collection

    def list_collections(
        self,
        user_id: str,
        *,
        include_public: bool = True,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ResearchCollectionDTO]:
        """List collections accessible to a user.

        Args:
            user_id: The requesting user.
            include_public: Whether to include public collections.
            limit: Maximum results to return.
            offset: Results to skip.

        Returns:
            List of accessible collections.
        """
        return self._collection_repository.list_all(
            user_id,
            include_public=include_public,
            limit=limit,
            offset=offset,
        )

    def update_collection(
        self,
        collection_id: str,
        user_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        is_public: bool | None = None,
    ) -> ResearchCollectionDTO:
        """Update collection metadata.

        Args:
            collection_id: The collection to update.
            user_id: User performing the update.
            name: New name if changing.
            description: New description if changing.
            is_public: New visibility if changing.

        Returns:
            The updated collection.

        Raises:
            CollectionNotFoundError: If collection doesn't exist.
            UnauthorizedCollectionAccessError: If user lacks permission.
        """
        # Verify ownership
        collection = self._collection_repository.get_by_id(collection_id)
        if collection is None:
            raise CollectionNotFoundError(collection_id)

        if collection.user_id != user_id:
            raise UnauthorizedCollectionAccessError(user_id, collection_id)

        result = self._collection_repository.update(
            collection_id,
            name=name,
            description=description,
            is_public=is_public,
        )
        if result is None:
            raise CollectionNotFoundError(collection_id)
        return result

    def delete_collection(self, collection_id: str, user_id: str) -> None:
        """Delete a collection and all its items.

        Args:
            collection_id: The collection to delete.
            user_id: User performing the deletion.

        Raises:
            CollectionNotFoundError: If collection doesn't exist.
            UnauthorizedCollectionAccessError: If user lacks permission.
        """
        # Verify ownership
        collection = self._collection_repository.get_by_id(collection_id)
        if collection is None:
            raise CollectionNotFoundError(collection_id)

        if collection.user_id != user_id:
            raise UnauthorizedCollectionAccessError(user_id, collection_id)

        self._collection_repository.delete(collection_id)

    # Item management ----------------------------------------------------------

    def add_item(
        self,
        collection_id: str,
        user_id: str,
        item_type: CollectionItemType,
        item_id: str,
        *,
        notes: str | None = None,
        position: int | None = None,
        validate_exists: bool = True,
    ) -> CollectionItemDTO:
        """Add an item to a collection.

        Args:
            collection_id: Target collection.
            user_id: User adding the item.
            item_type: Type of item being added.
            item_id: ID of the item to add.
            notes: Optional notes about the item.
            position: Optional position in the collection.
            validate_exists: Whether to verify the item exists.

        Returns:
            The created collection item.

        Raises:
            CollectionNotFoundError: If collection doesn't exist.
            UnauthorizedCollectionAccessError: If user lacks permission.
            ItemNotFoundError: If the referenced item doesn't exist.
        """
        # Verify collection access
        collection = self._collection_repository.get_by_id(collection_id)
        if collection is None:
            raise CollectionNotFoundError(collection_id)

        if collection.user_id != user_id:
            raise UnauthorizedCollectionAccessError(user_id, collection_id)

        # Validate item existence if requested
        if validate_exists:
            self._validate_item_exists(item_type, item_id)

        dto = AddCollectionItemDTO(
            collection_id=collection_id,
            item_type=item_type,
            item_id=item_id,
            notes=notes,
            position=position,
        )
        return self._collection_repository.add_item(dto)

    def remove_item(
        self,
        collection_id: str,
        item_id: str,
        user_id: str,
    ) -> None:
        """Remove an item from a collection.

        Args:
            collection_id: Collection containing the item.
            item_id: The item to remove.
            user_id: User performing the removal.

        Raises:
            CollectionNotFoundError: If collection doesn't exist.
            UnauthorizedCollectionAccessError: If user lacks permission.
            CollectionItemNotFoundError: If item doesn't exist in collection.
        """
        # Verify collection access
        collection = self._collection_repository.get_by_id(collection_id)
        if collection is None:
            raise CollectionNotFoundError(collection_id)

        if collection.user_id != user_id:
            raise UnauthorizedCollectionAccessError(user_id, collection_id)

        success = self._collection_repository.remove_item(collection_id, item_id)
        if not success:
            raise CollectionItemNotFoundError(item_id)

    def reorder_items(
        self,
        collection_id: str,
        user_id: str,
        item_ids: list[str],
    ) -> list[CollectionItemDTO]:
        """Reorder items in a collection.

        Args:
            collection_id: Collection to reorder.
            user_id: User performing the reorder.
            item_ids: Item IDs in the desired order.

        Returns:
            Updated list of items.

        Raises:
            CollectionNotFoundError: If collection doesn't exist.
            UnauthorizedCollectionAccessError: If user lacks permission.
        """
        # Verify collection access
        collection = self._collection_repository.get_by_id(collection_id)
        if collection is None:
            raise CollectionNotFoundError(collection_id)

        if collection.user_id != user_id:
            raise UnauthorizedCollectionAccessError(user_id, collection_id)

        return self._collection_repository.reorder_items(collection_id, item_ids)

    # Validation helpers -------------------------------------------------------

    def _validate_item_exists(
        self,
        item_type: CollectionItemType,
        item_id: str,
    ) -> None:
        """Verify that a referenced item exists.

        Args:
            item_type: Type of item to validate.
            item_id: ID of the item.

        Raises:
            ItemNotFoundError: If the item doesn't exist.
        """
        if item_type == CollectionItemType.DOCUMENT:
            if self._document_repository is not None:
                document = self._document_repository.get_by_id(item_id)
                if document is None:
                    raise ItemNotFoundError(item_type, item_id)
            # If no document repository, skip validation
            return

        # For other types (CHAT_SESSION, RESEARCH_NOTE, PASSAGE),
        # validation would require additional repositories.
        # Currently we skip validation for these types as the repositories
        # are not injected. This can be extended as needed.
        pass


__all__ = [
    "CollectionService",
    "CollectionNotFoundError",
    "CollectionItemNotFoundError",
    "ItemNotFoundError",
    "UnauthorizedCollectionAccessError",
]
