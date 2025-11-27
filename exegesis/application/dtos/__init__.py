"""Data Transfer Objects for application layer boundaries.

DTOs decouple the application layer from adapter implementation details,
allowing the service layer to work with domain-aligned objects rather than
ORM models directly.
"""

from .chat import ChatSessionDTO
from .collection import (
    AddCollectionItemDTO,
    CollectionItemDTO,
    CollectionItemType,
    CreateCollectionDTO,
    ResearchCollectionDTO,
)
from .discovery import (
    CorpusSnapshotDTO,
    DiscoveryDTO,
    DiscoveryListFilters,
)
from .document import (
    DocumentDTO,
    DocumentSummaryDTO,
    PassageDTO,
)
from .transcript import TranscriptSegmentDTO, TranscriptVideoDTO

__all__ = [
    "AddCollectionItemDTO",
    "ChatSessionDTO",
    "CollectionItemDTO",
    "CollectionItemType",
    "CorpusSnapshotDTO",
    "CreateCollectionDTO",
    "DiscoveryDTO",
    "DiscoveryListFilters",
    "DocumentDTO",
    "DocumentSummaryDTO",
    "PassageDTO",
    "ResearchCollectionDTO",
    "TranscriptSegmentDTO",
    "TranscriptVideoDTO",
]
