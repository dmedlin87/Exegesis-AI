"""Research collection endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from exegesis.adapters.persistence.collection_repository import (
    SQLAlchemyCollectionRepository,
)
from exegesis.adapters.persistence.document_repository import (
    SQLAlchemyDocumentRepository,
)
from exegesis.application.dtos.collection import CollectionItemType as DTOItemType
from exegesis.application.facades.database import get_session
from exegesis.application.services.collections.service import (
    CollectionItemNotFoundError,
    CollectionNotFoundError,
    CollectionService,
    ItemNotFoundError,
    UnauthorizedCollectionAccessError,
)
from exegesis.application.core.security import Principal

from ..adapters.security import require_principal
from ..core.errors import RetrievalError, Severity
from ..models.collections import (
    AddCollectionItemRequest,
    CollectionDetailResponse,
    CollectionItemResponse,
    CollectionItemType,
    CollectionListResponse,
    CollectionSummaryResponse,
    CreateCollectionRequest,
    ReorderItemsRequest,
    UpdateCollectionRequest,
)

router = APIRouter()


# -----------------------------------------------------------------------------
# Error response definitions
# -----------------------------------------------------------------------------

_COLLECTION_NOT_FOUND_RESPONSE = {
    status.HTTP_404_NOT_FOUND: {"description": "Collection not found"}
}

_COLLECTION_ITEM_NOT_FOUND_RESPONSE = {
    status.HTTP_404_NOT_FOUND: {"description": "Collection or item not found"}
}


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _require_user_subject(principal: Principal) -> str:
    """Extract user subject from principal, raising 403 if missing."""
    subject = principal.get("subject")
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Missing principal"
        )
    return subject


def _get_collection_service(session: Session) -> CollectionService:
    """Factory for constructing the collection service with dependencies."""
    collection_repo = SQLAlchemyCollectionRepository(session)
    document_repo = SQLAlchemyDocumentRepository(session)
    return CollectionService(
        collection_repo,
        document_repository=document_repo,
    )


def _handle_collection_errors(func):
    """Decorator to translate service exceptions to HTTP errors."""

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except CollectionNotFoundError as exc:
            raise RetrievalError(
                str(exc),
                code="COLLECTION_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
                severity=Severity.USER,
                hint="Verify the collection ID is correct.",
            ) from exc
        except CollectionItemNotFoundError as exc:
            raise RetrievalError(
                str(exc),
                code="COLLECTION_ITEM_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
                severity=Severity.USER,
                hint="Verify the item exists in the collection.",
            ) from exc
        except ItemNotFoundError as exc:
            raise RetrievalError(
                str(exc),
                code="REFERENCED_ITEM_NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND,
                severity=Severity.USER,
                hint=f"The referenced {exc.item_type.value} does not exist.",
            ) from exc
        except UnauthorizedCollectionAccessError as exc:
            raise RetrievalError(
                str(exc),
                code="COLLECTION_ACCESS_DENIED",
                status_code=status.HTTP_403_FORBIDDEN,
                severity=Severity.USER,
                hint="You do not have permission to access this collection.",
            ) from exc

    return wrapper


# -----------------------------------------------------------------------------
# Collection CRUD endpoints
# -----------------------------------------------------------------------------


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=CollectionDetailResponse,
)
def create_collection(
    payload: CreateCollectionRequest,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require_principal),
) -> CollectionDetailResponse:
    """Create a new research collection."""
    user_id = _require_user_subject(principal)
    service = _get_collection_service(session)

    collection = service.create_collection(
        user_id=user_id,
        name=payload.name,
        description=payload.description,
        is_public=payload.is_public,
    )

    return CollectionDetailResponse(
        id=collection.id,
        user_id=collection.user_id,
        name=collection.name,
        description=collection.description,
        is_public=collection.is_public,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
        items=[
            CollectionItemResponse(
                id=item.id,
                collection_id=item.collection_id,
                item_type=CollectionItemType(item.item_type.value),
                item_id=item.item_id,
                notes=item.notes,
                position=item.position,
                created_at=item.created_at,
            )
            for item in collection.items
        ],
    )


@router.get("/", response_model=CollectionListResponse)
def list_collections(
    include_public: bool = Query(default=True, description="Include public collections"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    principal: Principal = Depends(require_principal),
) -> CollectionListResponse:
    """List collections accessible to the current user."""
    user_id = _require_user_subject(principal)
    service = _get_collection_service(session)

    collections = service.list_collections(
        user_id=user_id,
        include_public=include_public,
        limit=limit,
        offset=offset,
    )

    items = [
        CollectionSummaryResponse(
            id=c.id,
            user_id=c.user_id,
            name=c.name,
            description=c.description,
            is_public=c.is_public,
            item_count=len(c.items),
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in collections
    ]

    return CollectionListResponse(
        items=items,
        total=len(items),  # Service doesn't return total count; use items length
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{collection_id}",
    response_model=CollectionDetailResponse,
    responses=_COLLECTION_NOT_FOUND_RESPONSE,
)
def get_collection(
    collection_id: str,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require_principal),
) -> CollectionDetailResponse:
    """Get collection details including all items."""
    user_id = _require_user_subject(principal)
    service = _get_collection_service(session)

    try:
        collection = service.get_collection(collection_id, user_id=user_id)
    except CollectionNotFoundError as exc:
        raise RetrievalError(
            str(exc),
            code="COLLECTION_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            severity=Severity.USER,
            hint="Verify the collection ID is correct.",
        ) from exc

    return CollectionDetailResponse(
        id=collection.id,
        user_id=collection.user_id,
        name=collection.name,
        description=collection.description,
        is_public=collection.is_public,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
        items=[
            CollectionItemResponse(
                id=item.id,
                collection_id=item.collection_id,
                item_type=CollectionItemType(item.item_type.value),
                item_id=item.item_id,
                notes=item.notes,
                position=item.position,
                created_at=item.created_at,
            )
            for item in collection.items
        ],
    )


@router.patch(
    "/{collection_id}",
    response_model=CollectionDetailResponse,
    responses=_COLLECTION_NOT_FOUND_RESPONSE,
)
def update_collection(
    collection_id: str,
    payload: UpdateCollectionRequest,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require_principal),
) -> CollectionDetailResponse:
    """Update collection metadata."""
    user_id = _require_user_subject(principal)
    service = _get_collection_service(session)

    try:
        collection = service.update_collection(
            collection_id=collection_id,
            user_id=user_id,
            name=payload.name,
            description=payload.description,
            is_public=payload.is_public,
        )
    except CollectionNotFoundError as exc:
        raise RetrievalError(
            str(exc),
            code="COLLECTION_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            severity=Severity.USER,
            hint="Verify the collection ID is correct.",
        ) from exc
    except UnauthorizedCollectionAccessError as exc:
        raise RetrievalError(
            str(exc),
            code="COLLECTION_ACCESS_DENIED",
            status_code=status.HTTP_403_FORBIDDEN,
            severity=Severity.USER,
            hint="You do not have permission to modify this collection.",
        ) from exc

    return CollectionDetailResponse(
        id=collection.id,
        user_id=collection.user_id,
        name=collection.name,
        description=collection.description,
        is_public=collection.is_public,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
        items=[
            CollectionItemResponse(
                id=item.id,
                collection_id=item.collection_id,
                item_type=CollectionItemType(item.item_type.value),
                item_id=item.item_id,
                notes=item.notes,
                position=item.position,
                created_at=item.created_at,
            )
            for item in collection.items
        ],
    )


@router.delete(
    "/{collection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_COLLECTION_NOT_FOUND_RESPONSE,
)
def delete_collection(
    collection_id: str,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require_principal),
) -> Response:
    """Delete a collection and all its items."""
    user_id = _require_user_subject(principal)
    service = _get_collection_service(session)

    try:
        service.delete_collection(collection_id, user_id)
    except CollectionNotFoundError as exc:
        raise RetrievalError(
            str(exc),
            code="COLLECTION_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            severity=Severity.USER,
            hint="Verify the collection ID is correct.",
        ) from exc
    except UnauthorizedCollectionAccessError as exc:
        raise RetrievalError(
            str(exc),
            code="COLLECTION_ACCESS_DENIED",
            status_code=status.HTTP_403_FORBIDDEN,
            severity=Severity.USER,
            hint="You do not have permission to delete this collection.",
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# -----------------------------------------------------------------------------
# Collection item endpoints
# -----------------------------------------------------------------------------


@router.post(
    "/{collection_id}/items",
    status_code=status.HTTP_201_CREATED,
    response_model=CollectionItemResponse,
    responses=_COLLECTION_NOT_FOUND_RESPONSE,
)
def add_collection_item(
    collection_id: str,
    payload: AddCollectionItemRequest,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require_principal),
) -> CollectionItemResponse:
    """Add an item to a collection."""
    user_id = _require_user_subject(principal)
    service = _get_collection_service(session)

    # Convert API enum to DTO enum
    dto_item_type = DTOItemType(payload.item_type.value)

    try:
        item = service.add_item(
            collection_id=collection_id,
            user_id=user_id,
            item_type=dto_item_type,
            item_id=payload.item_id,
            notes=payload.notes,
            position=payload.position,
            validate_exists=True,
        )
    except CollectionNotFoundError as exc:
        raise RetrievalError(
            str(exc),
            code="COLLECTION_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            severity=Severity.USER,
            hint="Verify the collection ID is correct.",
        ) from exc
    except UnauthorizedCollectionAccessError as exc:
        raise RetrievalError(
            str(exc),
            code="COLLECTION_ACCESS_DENIED",
            status_code=status.HTTP_403_FORBIDDEN,
            severity=Severity.USER,
            hint="You do not have permission to add items to this collection.",
        ) from exc
    except ItemNotFoundError as exc:
        raise RetrievalError(
            str(exc),
            code="REFERENCED_ITEM_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            severity=Severity.USER,
            hint=f"The referenced {exc.item_type.value} does not exist.",
        ) from exc

    return CollectionItemResponse(
        id=item.id,
        collection_id=item.collection_id,
        item_type=CollectionItemType(item.item_type.value),
        item_id=item.item_id,
        notes=item.notes,
        position=item.position,
        created_at=item.created_at,
    )


@router.delete(
    "/{collection_id}/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_COLLECTION_ITEM_NOT_FOUND_RESPONSE,
)
def remove_collection_item(
    collection_id: str,
    item_id: str,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require_principal),
) -> Response:
    """Remove an item from a collection."""
    user_id = _require_user_subject(principal)
    service = _get_collection_service(session)

    try:
        service.remove_item(collection_id, item_id, user_id)
    except CollectionNotFoundError as exc:
        raise RetrievalError(
            str(exc),
            code="COLLECTION_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            severity=Severity.USER,
            hint="Verify the collection ID is correct.",
        ) from exc
    except UnauthorizedCollectionAccessError as exc:
        raise RetrievalError(
            str(exc),
            code="COLLECTION_ACCESS_DENIED",
            status_code=status.HTTP_403_FORBIDDEN,
            severity=Severity.USER,
            hint="You do not have permission to remove items from this collection.",
        ) from exc
    except CollectionItemNotFoundError as exc:
        raise RetrievalError(
            str(exc),
            code="COLLECTION_ITEM_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            severity=Severity.USER,
            hint="Verify the item exists in the collection.",
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/{collection_id}/items/order",
    response_model=list[CollectionItemResponse],
    responses=_COLLECTION_NOT_FOUND_RESPONSE,
)
def reorder_collection_items(
    collection_id: str,
    payload: ReorderItemsRequest,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require_principal),
) -> list[CollectionItemResponse]:
    """Reorder items in a collection."""
    user_id = _require_user_subject(principal)
    service = _get_collection_service(session)

    try:
        items = service.reorder_items(collection_id, user_id, payload.item_ids)
    except CollectionNotFoundError as exc:
        raise RetrievalError(
            str(exc),
            code="COLLECTION_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            severity=Severity.USER,
            hint="Verify the collection ID is correct.",
        ) from exc
    except UnauthorizedCollectionAccessError as exc:
        raise RetrievalError(
            str(exc),
            code="COLLECTION_ACCESS_DENIED",
            status_code=status.HTTP_403_FORBIDDEN,
            severity=Severity.USER,
            hint="You do not have permission to reorder items in this collection.",
        ) from exc

    return [
        CollectionItemResponse(
            id=item.id,
            collection_id=item.collection_id,
            item_type=CollectionItemType(item.item_type.value),
            item_id=item.item_id,
            notes=item.notes,
            position=item.position,
            created_at=item.created_at,
        )
        for item in items
    ]
