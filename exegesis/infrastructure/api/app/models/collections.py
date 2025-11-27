"""Collection schemas for API request/response models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import Field

from .base import APIModel


class CollectionItemType(str, Enum):
    """Types of items that can be added to a collection."""

    DOCUMENT = "document"
    CHAT_SESSION = "chat_session"
    RESEARCH_NOTE = "research_note"
    PASSAGE = "passage"


# -----------------------------------------------------------------------------
# Request schemas
# -----------------------------------------------------------------------------


class CreateCollectionRequest(APIModel):
    """Request body for creating a new collection."""

    name: str = Field(min_length=1, max_length=255, description="Collection name")
    description: str | None = Field(
        default=None, max_length=2000, description="Optional description"
    )
    is_public: bool = Field(default=False, description="Whether the collection is publicly visible")


class UpdateCollectionRequest(APIModel):
    """Request body for updating collection metadata."""

    name: str | None = Field(
        default=None, min_length=1, max_length=255, description="New collection name"
    )
    description: str | None = Field(
        default=None, max_length=2000, description="New description"
    )
    is_public: bool | None = Field(
        default=None, description="New visibility setting"
    )


class AddCollectionItemRequest(APIModel):
    """Request body for adding an item to a collection."""

    item_type: CollectionItemType = Field(description="Type of item to add")
    item_id: str = Field(min_length=1, description="ID of the item to add")
    notes: str | None = Field(
        default=None, max_length=5000, description="Optional notes about the item"
    )
    position: int | None = Field(
        default=None, ge=0, description="Optional position in the collection"
    )


class ReorderItemsRequest(APIModel):
    """Request body for reordering items in a collection."""

    item_ids: list[str] = Field(
        min_length=1, description="Item IDs in the desired order"
    )


# -----------------------------------------------------------------------------
# Response schemas
# -----------------------------------------------------------------------------


class CollectionItemResponse(APIModel):
    """Response schema for a collection item."""

    id: str
    collection_id: str
    item_type: CollectionItemType
    item_id: str
    notes: str | None = None
    position: int
    created_at: datetime


class CollectionSummaryResponse(APIModel):
    """Abbreviated collection info for list responses."""

    id: str
    user_id: str
    name: str
    description: str | None = None
    is_public: bool
    item_count: int = Field(default=0, description="Number of items in the collection")
    created_at: datetime
    updated_at: datetime


class CollectionDetailResponse(APIModel):
    """Full collection details including items."""

    id: str
    user_id: str
    name: str
    description: str | None = None
    is_public: bool
    created_at: datetime
    updated_at: datetime
    items: list[CollectionItemResponse] = Field(default_factory=list)


class CollectionListResponse(APIModel):
    """Paginated list of collections."""

    items: list[CollectionSummaryResponse]
    total: int
    limit: int
    offset: int


__all__ = [
    "CollectionItemType",
    "CreateCollectionRequest",
    "UpdateCollectionRequest",
    "AddCollectionItemRequest",
    "ReorderItemsRequest",
    "CollectionItemResponse",
    "CollectionSummaryResponse",
    "CollectionDetailResponse",
    "CollectionListResponse",
]
