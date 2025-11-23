import pytest
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch
from theo.infrastructure.api.app.mcp.tools import handle_note_write, MCPToolError
from theo.infrastructure.api.app.models.research import ResearchNote as ResearchNoteSchema

def test_handle_note_write_creates_note(integration_session):
    payload = {
        "osis": "Matt.1.1",
        "body": "This is a test note",
        "title": "Test Note",
        "commit": True
    }

    # Mock get_research_service to return a mock service
    with patch("theo.infrastructure.api.app.mcp.tools.get_research_service") as mock_get_service:
        mock_service = Mock()
        mock_get_service.return_value = mock_service

        mock_note = Mock()
        mock_note.id = "note-123"
        mock_note.osis = "Matt.1.1"
        mock_note.body = "This is a test note"
        mock_note.title = "Test Note"
        mock_note.stance = None
        mock_note.claim_type = None
        mock_note.confidence = None  # Explicitly set to None to avoid Mock object
        mock_note.tags = []
        mock_note.evidences = []
        mock_note.created_at = datetime.now()
        mock_note.updated_at = datetime.now()

        mock_service.create_note.return_value = mock_note

        result = handle_note_write(integration_session, payload)

        assert isinstance(result, ResearchNoteSchema)
        assert result.osis == "Matt.1.1"
        assert result.body == "This is a test note"

        mock_service.create_note.assert_called_once()
        draft = mock_service.create_note.call_args[0][0]
        assert draft.osis == "Matt.1.1"
        assert draft.body == "This is a test note"

def test_handle_note_write_missing_osis():
    payload = {
        "body": "No OSIS"
    }
    session = Mock()

    with pytest.raises(MCPToolError):
        handle_note_write(session, payload)

def test_handle_note_write_resolves_doc_id(integration_session):
    # Mock _resolve_document_osis
    with patch("theo.infrastructure.api.app.mcp.tools._resolve_document_osis") as mock_resolve:
        mock_resolve.return_value = "John.1.1"

        payload = {
            "doc_id": "doc-123",
            "body": "Resolved OSIS",
            "commit": False,
            "osis": ""  # Required by schema, but empty to trigger doc_id resolution
        }

        with patch("theo.infrastructure.api.app.mcp.tools.get_research_service") as mock_get_service:
            mock_service = Mock()
            mock_get_service.return_value = mock_service

            mock_preview = ResearchNoteSchema(
                id="preview-id",
                osis="John.1.1",
                body="Resolved OSIS",
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            mock_service.preview_note.return_value = mock_preview

            result = handle_note_write(integration_session, payload)

            assert result.osis == "John.1.1"
            mock_resolve.assert_called_with(integration_session, "doc-123")
            mock_service.preview_note.assert_called_once()
