"""DTOs for research collection domain objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class CollectionItemType(str, Enum):
    """Types of items that can be added to a collection."""

    DOCUMENT = "document"
    CHAT_SESSION = "chat_session"
    RESEARCH_NOTE = "research_note"
    PASSAGE = "passage"


@dataclass(frozen=True)
class CollectionItemDTO:
    """Represents an item within a research collection."""

    id: str
    collection_id: str
    item_type: CollectionItemType
    item_id: str
    notes: str | None
    position: int
    created_at: datetime


@dataclass(frozen=True)
class ResearchCollectionDTO:
    """Application-layer representation of a research collection."""

    id: str
    user_id: str
    name: str
    description: str | None
    is_public: bool
    created_at: datetime
    updated_at: datetime
    items: list[CollectionItemDTO] = field(default_factory=list)


@dataclass
class CreateCollectionDTO:
    """Data required to create a new collection."""

    user_id: str
    name: str
    description: str | None = None
    is_public: bool = False


@dataclass
class AddCollectionItemDTO:
    """Data required to add an item to a collection."""

    collection_id: str
    item_type: CollectionItemType
    item_id: str
    notes: str | None = None
    position: int | None = None


__all__ = [
    "CollectionItemType",
    "CollectionItemDTO",
    "ResearchCollectionDTO",
    "CreateCollectionDTO",
    "AddCollectionItemDTO",
]
