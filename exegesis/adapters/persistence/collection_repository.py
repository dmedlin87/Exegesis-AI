"""SQLAlchemy implementation of CollectionRepository."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from exegesis.application.dtos.collection import (
    AddCollectionItemDTO,
    CollectionItemDTO,
    CollectionItemType,
    CreateCollectionDTO,
    ResearchCollectionDTO,
)
from exegesis.application.core.observability import trace_repository_call
from exegesis.application.repositories.collection_repository import (
    CollectionRepository,
)

from .base_repository import BaseRepository
from .models import (
    CollectionItem,
    CollectionItemType as ModelCollectionItemType,
    ResearchCollection,
)


def _item_to_dto(item: CollectionItem) -> CollectionItemDTO:
    """Convert ORM CollectionItem to DTO."""
    return CollectionItemDTO(
        id=item.id,
        collection_id=item.collection_id,
        item_type=CollectionItemType(item.item_type.value),
        item_id=item.item_id,
        notes=item.notes,
        position=item.position,
        created_at=item.created_at,
    )


def _collection_to_dto(collection: ResearchCollection) -> ResearchCollectionDTO:
    """Convert ORM ResearchCollection to DTO."""
    items = [_item_to_dto(item) for item in (collection.items or [])]
    return ResearchCollectionDTO(
        id=collection.id,
        user_id=collection.user_id,
        name=collection.name,
        description=collection.description,
        is_public=collection.is_public,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
        items=items,
    )


class SQLAlchemyCollectionRepository(
    BaseRepository[ResearchCollection], CollectionRepository
):
    """Collection repository backed by a SQLAlchemy session."""

    def __init__(self, session: Session):
        super().__init__(session)

    def create(self, dto: CreateCollectionDTO) -> ResearchCollectionDTO:
        """Create a new research collection."""
        with trace_repository_call(
            "collection",
            "create",
            attributes={"user_id": dto.user_id, "name": dto.name},
        ) as trace:
            collection = ResearchCollection(
                user_id=dto.user_id,
                name=dto.name,
                description=dto.description,
                is_public=dto.is_public,
            )
            self.add(collection)
            self.flush()
            trace.record_result_count(1)
            return _collection_to_dto(collection)

    def get_by_id(
        self, collection_id: str, *, user_id: str | None = None
    ) -> ResearchCollectionDTO | None:
        """Retrieve a collection by its identifier."""
        with trace_repository_call(
            "collection",
            "get_by_id",
            attributes={"collection_id": collection_id, "user_id": user_id},
        ) as trace:
            stmt = (
                select(ResearchCollection)
                .options(selectinload(ResearchCollection.items))
                .where(ResearchCollection.id == collection_id)
            )

            # Apply access control
            if user_id is not None:
                stmt = stmt.where(
                    or_(
                        ResearchCollection.user_id == user_id,
                        ResearchCollection.is_public == True,  # noqa: E712
                    )
                )

            collection = self.scalar_one_or_none(stmt)
            trace.set_attribute("hit", collection is not None)
            trace.record_result_count(1 if collection else 0)
            return _collection_to_dto(collection) if collection else None

    def list_all(
        self,
        user_id: str,
        *,
        include_public: bool = True,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ResearchCollectionDTO]:
        """List collections accessible to a user."""
        with trace_repository_call(
            "collection",
            "list_all",
            attributes={
                "user_id": user_id,
                "include_public": include_public,
                "limit": limit,
                "offset": offset,
            },
        ) as trace:
            stmt = select(ResearchCollection).options(
                selectinload(ResearchCollection.items)
            )

            if include_public:
                stmt = stmt.where(
                    or_(
                        ResearchCollection.user_id == user_id,
                        ResearchCollection.is_public == True,  # noqa: E712
                    )
                )
            else:
                stmt = stmt.where(ResearchCollection.user_id == user_id)

            stmt = stmt.order_by(ResearchCollection.updated_at.desc())

            if limit is not None:
                stmt = stmt.limit(limit)
            if offset is not None:
                stmt = stmt.offset(offset)

            collections = self.scalars(stmt).all()
            trace.record_result_count(len(collections))
            return [_collection_to_dto(c) for c in collections]

    def update(
        self,
        collection_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        is_public: bool | None = None,
    ) -> ResearchCollectionDTO | None:
        """Update collection metadata."""
        with trace_repository_call(
            "collection",
            "update",
            attributes={"collection_id": collection_id},
        ) as trace:
            collection = self.get(ResearchCollection, collection_id)
            if collection is None:
                trace.set_attribute("hit", False)
                trace.record_result_count(0)
                return None

            if name is not None:
                collection.name = name
            if description is not None:
                collection.description = description
            if is_public is not None:
                collection.is_public = is_public

            collection.updated_at = datetime.now(UTC)
            self.flush()

            # Reload with items
            stmt = (
                select(ResearchCollection)
                .options(selectinload(ResearchCollection.items))
                .where(ResearchCollection.id == collection_id)
            )
            collection = self.scalar_one_or_none(stmt)
            trace.set_attribute("hit", True)
            trace.record_result_count(1)
            return _collection_to_dto(collection) if collection else None

    def delete(self, collection_id: str) -> bool:
        """Delete a collection and all its items."""
        with trace_repository_call(
            "collection",
            "delete",
            attributes={"collection_id": collection_id},
        ) as trace:
            collection = self.get(ResearchCollection, collection_id)
            if collection is None:
                trace.set_attribute("hit", False)
                trace.record_result_count(0)
                return False

            self._session.delete(collection)
            self.flush()
            trace.set_attribute("hit", True)
            trace.record_result_count(1)
            return True

    def add_item(self, dto: AddCollectionItemDTO) -> CollectionItemDTO:
        """Add an item to a collection."""
        with trace_repository_call(
            "collection",
            "add_item",
            attributes={
                "collection_id": dto.collection_id,
                "item_type": dto.item_type.value,
                "item_id": dto.item_id,
            },
        ) as trace:
            # Determine position
            if dto.position is not None:
                position = dto.position
            else:
                # Get max position and add 1
                stmt = (
                    select(CollectionItem.position)
                    .where(CollectionItem.collection_id == dto.collection_id)
                    .order_by(CollectionItem.position.desc())
                    .limit(1)
                )
                max_position = self.scalar_first(stmt)
                position = (max_position or 0) + 1

            item = CollectionItem(
                collection_id=dto.collection_id,
                item_type=ModelCollectionItemType(dto.item_type.value),
                item_id=dto.item_id,
                notes=dto.notes,
                position=position,
            )
            self.add(item)
            self.flush()
            trace.record_result_count(1)
            return _item_to_dto(item)

    def remove_item(self, collection_id: str, item_id: str) -> bool:
        """Remove an item from a collection."""
        with trace_repository_call(
            "collection",
            "remove_item",
            attributes={"collection_id": collection_id, "item_id": item_id},
        ) as trace:
            stmt = select(CollectionItem).where(
                CollectionItem.collection_id == collection_id,
                CollectionItem.id == item_id,
            )
            item = self.scalar_one_or_none(stmt)
            if item is None:
                trace.set_attribute("hit", False)
                trace.record_result_count(0)
                return False

            self._session.delete(item)
            self.flush()
            trace.set_attribute("hit", True)
            trace.record_result_count(1)
            return True

    def get_item(
        self, collection_id: str, item_id: str
    ) -> CollectionItemDTO | None:
        """Retrieve a specific item from a collection."""
        with trace_repository_call(
            "collection",
            "get_item",
            attributes={"collection_id": collection_id, "item_id": item_id},
        ) as trace:
            stmt = select(CollectionItem).where(
                CollectionItem.collection_id == collection_id,
                CollectionItem.id == item_id,
            )
            item = self.scalar_one_or_none(stmt)
            trace.set_attribute("hit", item is not None)
            trace.record_result_count(1 if item else 0)
            return _item_to_dto(item) if item else None

    def reorder_items(
        self, collection_id: str, item_ids: list[str]
    ) -> list[CollectionItemDTO]:
        """Reorder items in a collection."""
        with trace_repository_call(
            "collection",
            "reorder_items",
            attributes={"collection_id": collection_id, "item_count": len(item_ids)},
        ) as trace:
            stmt = select(CollectionItem).where(
                CollectionItem.collection_id == collection_id
            )
            items = {item.id: item for item in self.scalars(stmt).all()}

            # Update positions based on provided order
            for position, item_id in enumerate(item_ids):
                if item_id in items:
                    items[item_id].position = position

            self.flush()

            # Return items in new order
            result = sorted(items.values(), key=lambda x: x.position)
            trace.record_result_count(len(result))
            return [_item_to_dto(item) for item in result]


__all__ = ["SQLAlchemyCollectionRepository"]
