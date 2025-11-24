from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from theo.application.facades.database import get_session
from theo.domain import Document, DocumentId, DocumentMetadata
from theo.application.services.bootstrap import resolve_application
from theo.infrastructure.api.app.main import app
from theo.infrastructure.api.app.retrieval.retriever import documents as documents_retriever
from theo.infrastructure.api.app.routes import documents as documents_route


@pytest.mark.integration
def test_documents_api_with_real_database_transaction(
    sqlite_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensure document APIs operate against a live transactional database."""

    real_get_document = documents_retriever.get_document

    def _get_document_with_missing(session: Session, document_id: str):
        if document_id == "missing":
            raise KeyError("Document missing")
        return real_get_document(session, document_id)

    monkeypatch.setattr(
        documents_retriever, "get_document", _get_document_with_missing
    )
    monkeypatch.setattr(documents_route, "get_document", _get_document_with_missing)

    # Ensure no auto-generated dev key interferes with our configured test API key
    from theo.application.facades.runtime import clear_generated_dev_key
    clear_generated_dev_key()

    container, registry = resolve_application()

    document = Document(
        id=DocumentId("doc-biblical"),
        metadata=DocumentMetadata(
            title="Genesis Commentary",
            source="manuscript",
            language="hebrew",
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ),
        scripture_refs=("Gen.1.1",),
        tags=("creation", "theology"),
        checksum="abc123",
    )
    # Patch get_session so the service layer uses our transaction-bound session
    monkeypatch.setattr("theo.application.facades.database.get_session", lambda: sqlite_session)

    # Patch _session_scope to use our session and prevent commits
    from contextlib import contextmanager
    from unittest.mock import patch

    @contextmanager
    def _mock_session_scope(registry):
        with patch.object(sqlite_session, "commit"):
            yield sqlite_session

    monkeypatch.setattr("theo.application.services.bootstrap._session_scope", _mock_session_scope)

    container.ingest_document(document)

    def _override_session() -> Iterator[Session]:
        # Use the session from the fixture which is wrapped in a transaction
        yield sqlite_session

    app.dependency_overrides[get_session] = _override_session
    try:
        with TestClient(app) as client:
            headers = {"X-API-Key": "pytest-default-key"}
            response = client.get("/documents", headers=headers)
            assert response.status_code == 200
            payload = response.json()
            assert payload["items"], "Expected document results"
            payload = response.json()
            assert payload["items"], "Expected document results"

            # Find our document in the results (there might be baseline docs)
            found_doc = next((item for item in payload["items"] if item["id"] == str(document.id)), None)
            assert found_doc is not None, f"Document {document.id} not found in results"

            assert found_doc["id"] == str(document.id)
            assert found_doc["title"] == document.metadata.title
            assert found_doc["collection"] == document.metadata.source

            missing = client.get("/documents/missing", headers=headers)
            assert missing.status_code == 404
            detail = missing.json()
            assert detail["error"]["code"] == "RETRIEVAL_DOCUMENT_NOT_FOUND"
            assert "Document missing" in detail["detail"]
    finally:
        app.dependency_overrides.pop(get_session, None)
