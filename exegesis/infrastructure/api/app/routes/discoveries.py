"""API endpoints surfacing user discoveries."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from exegesis.adapters.persistence.discovery_repository import SQLAlchemyDiscoveryRepository
from exegesis.adapters.persistence.document_repository import SQLAlchemyDocumentRepository
from exegesis.application.facades.database import get_session
from exegesis.application.repositories import DiscoveryRepository, DocumentRepository

from ..research.discoveries import DiscoveryService
from ..models.discoveries import (
    DiscoveryFeedbackRequest,
    DiscoveryGraphResponse,
    DiscoveryListResponse,
    DiscoveryResponse,
    DiscoveryStats,
    GraphLink,
    GraphNode,
)
from exegesis.application.core.security import Principal

from ..adapters.security import require_principal

router = APIRouter()


def _require_user_subject(principal: Principal) -> str:
    subject = principal.get("subject")
    if not subject:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing principal")
    return subject


def get_discovery_service(
    session: Session = Depends(get_session),
) -> DiscoveryService:
    discovery_repo: DiscoveryRepository = SQLAlchemyDiscoveryRepository(session)
    document_repo: DocumentRepository = SQLAlchemyDocumentRepository(session)
    return DiscoveryService(discovery_repo, document_repo)


def _build_stats(discoveries: list[DiscoveryResponse]) -> DiscoveryStats:
    total = len(discoveries)
    unviewed = sum(1 for item in discoveries if not item.viewed)
    by_type: dict[str, int] = {}
    for item in discoveries:
        by_type[item.type] = by_type.get(item.type, 0) + 1
    average_confidence = 0.0
    if total:
        average_confidence = sum(item.confidence for item in discoveries) / total
    return DiscoveryStats(
        total=total,
        unviewed=unviewed,
        byType=by_type,
        averageConfidence=round(average_confidence, 4),
    )


@router.get("/", response_model=DiscoveryListResponse)
def list_discoveries(
    discovery_type: str | None = Query(default=None),
    viewed: bool | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(require_principal),
    service: DiscoveryService = Depends(get_discovery_service),
) -> DiscoveryListResponse:
    user_id = _require_user_subject(principal)
    records = service.list(
        user_id,
        discovery_type=discovery_type,
        viewed=viewed,
        limit=limit,
        offset=offset,
    )
    payload = [DiscoveryResponse.model_validate(record) for record in records]
    stats = _build_stats(payload)
    return DiscoveryListResponse(discoveries=payload, stats=stats)


@router.post("/{discovery_id}/view", status_code=status.HTTP_204_NO_CONTENT)
def mark_discovery_viewed(
    discovery_id: int,
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
    service: DiscoveryService = Depends(get_discovery_service),
) -> Response:
    user_id = _require_user_subject(principal)
    try:
        service.mark_viewed(user_id, discovery_id)
        session.commit()
    except LookupError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discovery not found") from exc
    except Exception:
        session.rollback()
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{discovery_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
def submit_discovery_feedback(
    discovery_id: int,
    payload: DiscoveryFeedbackRequest,
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
    service: DiscoveryService = Depends(get_discovery_service),
) -> Response:
    user_id = _require_user_subject(principal)
    reaction = "helpful" if payload.helpful else "not_helpful"
    try:
        service.set_feedback(user_id, discovery_id, reaction)
        session.commit()
    except LookupError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discovery not found") from exc
    except Exception:
        session.rollback()
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{discovery_id}", status_code=status.HTTP_204_NO_CONTENT)
def dismiss_discovery(
    discovery_id: int,
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
    service: DiscoveryService = Depends(get_discovery_service),
) -> Response:
    user_id = _require_user_subject(principal)
    try:
        service.dismiss(user_id, discovery_id)
        session.commit()
    except LookupError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discovery not found") from exc
    except Exception:
        session.rollback()
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/graph", response_model=DiscoveryGraphResponse)
def get_discovery_graph(
    discovery_type: str | None = Query(default=None),
    viewed: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    principal: Principal = Depends(require_principal),
    service: DiscoveryService = Depends(get_discovery_service),
) -> DiscoveryGraphResponse:
    """
    Return discoveries and their relationships as a graph structure.

    This endpoint returns only metadata (no full content bodies) for efficient visualization.
    Nodes represent discoveries and related evidence, links represent relationships.
    """
    user_id = _require_user_subject(principal)

    # Fetch discoveries with metadata only
    records = service.list(
        user_id,
        discovery_type=discovery_type,
        viewed=viewed,
        limit=limit,
        offset=0,
    )

    nodes: list[GraphNode] = []
    links: list[GraphLink] = []
    evidence_ids: set[str] = set()

    # Create discovery nodes
    for record in records:
        discovery_id = str(record.id)
        nodes.append(
            GraphNode(
                id=discovery_id,
                type="discovery",
                label=record.title,
                discoveryType=record.discovery_type,
                confidence=record.confidence,
                viewed=record.viewed,
            )
        )

        # Extract evidence nodes from metadata
        metadata = record.metadata if isinstance(record.metadata, dict) else {}

        # Handle contradiction discoveries
        if record.discovery_type == "contradiction":
            doc_a_id = metadata.get("document_a_id")
            doc_b_id = metadata.get("document_b_id")

            if doc_a_id:
                evidence_id = f"doc_{doc_a_id}"
                if evidence_id not in evidence_ids:
                    nodes.append(
                        GraphNode(
                            id=evidence_id,
                            type="evidence",
                            label=metadata.get("document_a_title", f"Document {doc_a_id}"),
                        )
                    )
                    evidence_ids.add(evidence_id)
                links.append(
                    GraphLink(
                        source=discovery_id,
                        target=evidence_id,
                        type="contradicts",
                    )
                )

            if doc_b_id:
                evidence_id = f"doc_{doc_b_id}"
                if evidence_id not in evidence_ids:
                    nodes.append(
                        GraphNode(
                            id=evidence_id,
                            type="evidence",
                            label=metadata.get("document_b_title", f"Document {doc_b_id}"),
                        )
                    )
                    evidence_ids.add(evidence_id)
                links.append(
                    GraphLink(
                        source=discovery_id,
                        target=evidence_id,
                        type="contradicts",
                    )
                )

        # Handle anomaly discoveries
        elif record.discovery_type == "anomaly":
            doc_id = metadata.get("documentId")
            if doc_id:
                evidence_id = f"doc_{doc_id}"
                if evidence_id not in evidence_ids:
                    nodes.append(
                        GraphNode(
                            id=evidence_id,
                            type="evidence",
                            label=f"Document {doc_id}",
                        )
                    )
                    evidence_ids.add(evidence_id)
                links.append(
                    GraphLink(
                        source=discovery_id,
                        target=evidence_id,
                        type="references",
                    )
                )

        # Handle gap discoveries
        elif record.discovery_type == "gap":
            related_docs = metadata.get("relatedDocuments", [])
            for doc_id in related_docs[:5]:  # Limit to 5 related docs per gap
                evidence_id = f"doc_{doc_id}"
                if evidence_id not in evidence_ids:
                    nodes.append(
                        GraphNode(
                            id=evidence_id,
                            type="evidence",
                            label=f"Document {doc_id}",
                        )
                    )
                    evidence_ids.add(evidence_id)
                links.append(
                    GraphLink(
                        source=discovery_id,
                        target=evidence_id,
                        type="references",
                    )
                )

        # Handle connection discoveries
        elif record.discovery_type == "connection":
            related_docs = metadata.get("relatedDocuments", [])
            for doc_id in related_docs[:5]:
                evidence_id = f"doc_{doc_id}"
                if evidence_id not in evidence_ids:
                    nodes.append(
                        GraphNode(
                            id=evidence_id,
                            type="evidence",
                            label=f"Document {doc_id}",
                        )
                    )
                    evidence_ids.add(evidence_id)
                links.append(
                    GraphLink(
                        source=discovery_id,
                        target=evidence_id,
                        type="connects",
                    )
                )

        # Handle generic related documents/verses
        related_docs = metadata.get("relatedDocuments")
        if related_docs and isinstance(related_docs, list):
            for doc_id in related_docs[:3]:
                evidence_id = f"doc_{doc_id}"
                if evidence_id not in evidence_ids:
                    nodes.append(
                        GraphNode(
                            id=evidence_id,
                            type="evidence",
                            label=f"Document {doc_id}",
                        )
                    )
                    evidence_ids.add(evidence_id)
                links.append(
                    GraphLink(
                        source=discovery_id,
                        target=evidence_id,
                        type="references",
                    )
                )

    return DiscoveryGraphResponse(nodes=nodes, links=links)


__all__ = ["router"]
