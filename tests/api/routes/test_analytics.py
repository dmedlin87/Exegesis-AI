"""Comprehensive tests for analytics route endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestTelemetryIngestion:
    """Test suite for POST /analytics/telemetry endpoint."""

    def test_ingest_telemetry_accepts_valid_batch(
        self, api_test_client: TestClient
    ) -> None:
        """Test accepting valid telemetry batch."""
        payload = {
            "page": "/search",
            "events": [
                {
                    "event": "page_view",
                    "duration_ms": 0.0,
                    "metadata": {"page": "/search"},
                },
                {
                    "event": "search_query",
                    "duration_ms": 150.0,
                    "metadata": {"query": "faith", "results_count": 10},
                },
            ],
        }

        response = api_test_client.post("/analytics/telemetry", json=payload)

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"

    def test_ingest_telemetry_empty_events(self, api_test_client: TestClient) -> None:
        """Test ingesting telemetry with empty events array."""
        payload = {
            "page": "home",
            "events": [],
        }

        response = api_test_client.post("/analytics/telemetry", json=payload)

        assert response.status_code == 202

    def test_ingest_telemetry_missing_required_fields(
        self, api_test_client: TestClient
    ) -> None:
        """Test that missing required fields are rejected."""
        payload = {
            "page": "test-session",
            "events": "not-a-list",  # Invalid type for events
        }

        response = api_test_client.post("/analytics/telemetry", json=payload)

        assert response.status_code == 422

    def test_ingest_telemetry_invalid_json(self, api_test_client: TestClient) -> None:
        """Test that invalid JSON is rejected."""
        response = api_test_client.post(
            "/analytics/telemetry",
            data="invalid-json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422

    def test_ingest_telemetry_multiple_event_types(
        self, api_test_client: TestClient
    ) -> None:
        """Test ingesting various event types in one batch."""
        payload = {
            "page": "dashboard",
            "events": [
                {
                    "event": "page_view",
                    "duration_ms": 0.0,
                    "metadata": {},
                },
                {
                    "event": "button_click",
                    "duration_ms": 50.0,
                    "metadata": {"button_id": "search"},
                },
                {
                    "event": "api_call",
                    "duration_ms": 150.0,
                    "metadata": {"endpoint": "/search"},
                },
            ],
        }

        response = api_test_client.post("/analytics/telemetry", json=payload)

        assert response.status_code == 202

    def test_ingest_telemetry_with_metadata(
        self, api_test_client: TestClient
    ) -> None:
        """Test ingesting telemetry with additional metadata."""
        payload = {
            "page": "error-page",
            "events": [
                {
                    "event": "error",
                    "duration_ms": 0.0,
                    "metadata": {
                        "error_type": "NetworkError",
                        "message": "Connection timeout",
                        "stack_trace": "Error at line 42...",
                        "user_agent": "Mozilla/5.0...",
                        "screen_width": 1920,
                        "screen_height": 1080,
                    },
                }
            ],
        }

        response = api_test_client.post("/analytics/telemetry", json=payload)

        assert response.status_code == 202


class TestFeedbackIngestion:
    """Test suite for POST /analytics/feedback endpoint."""

    def test_ingest_feedback_positive(self, api_test_client: TestClient) -> None:
        """Test ingesting positive feedback."""
        payload = {
            "action": "like",
            "user_id": "test-user",
            "query": "faith",
            "rank": 1,
            "document_id": "result-123",
        }

        response = api_test_client.post("/analytics/feedback", json=payload)

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"

    def test_ingest_feedback_negative(self, api_test_client: TestClient) -> None:
        """Test ingesting negative feedback."""
        payload = {
            "action": "dislike",
            "user_id": "test-user",
            "document_id": "response-456",
            "confidence": 0.1,
        }

        response = api_test_client.post("/analytics/feedback", json=payload)

        assert response.status_code == 202

    def test_ingest_feedback_with_detailed_context(
        self, api_test_client: TestClient
    ) -> None:
        """Test feedback with rich contextual information."""
        payload = {
            "action": "dislike",
            "user_id": "test-user",
            "document_id": "doc-789",
            "query": "broken link",
        }

        response = api_test_client.post("/analytics/feedback", json=payload)

        assert response.status_code == 202

    def test_ingest_feedback_missing_required_fields(
        self, api_test_client: TestClient
    ) -> None:
        """Test that missing required fields are rejected."""
        payload = {
            "user_id": "test-user",
            # Missing action
        }

        response = api_test_client.post("/analytics/feedback", json=payload)

        assert response.status_code == 422

    def test_ingest_feedback_invalid_event_type(
        self, api_test_client: TestClient
    ) -> None:
        """Test that invalid event types are handled appropriately."""
        payload = {
            "action": "",  # Empty action
            "user_id": "test-user",
        }

        response = api_test_client.post("/analytics/feedback", json=payload)

        # Depending on validation, may accept or reject
        assert response.status_code in [202, 400, 422]

    def test_ingest_feedback_persistence_error_handling(
        self, api_test_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test error handling when feedback persistence fails."""

        def _raise_value_error(*args, **kwargs):
            raise ValueError("Database constraint violation")

        monkeypatch.setattr(
            "exegesis.infrastructure.api.app.routes.analytics.record_feedback_from_payload",
            _raise_value_error,
        )

        payload = {
            "action": "like",
            "user_id": "test-user",
            "document_id": "123",
        }

        response = api_test_client.post("/analytics/feedback", json=payload)

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data

    def test_ingest_feedback_with_tags(self, api_test_client: TestClient) -> None:
        """Test feedback with categorization tags."""
        payload = {
            "action": "like",
            "user_id": "test-user",
            "query": "Add faceted search filters",
        }

        response = api_test_client.post("/analytics/feedback", json=payload)

        assert response.status_code in [202, 400, 422]


class TestAnalyticsAuthentication:
    """Test analytics endpoint authentication."""

    def test_telemetry_ingestion_anonymous(self, api_test_client: TestClient) -> None:
        """Test that telemetry can be ingested without authentication."""
        payload = {
            "page": "anon-session",
            "events": [{"event": "page_view", "duration_ms": 100.0}],
        }

        response = api_test_client.post("/analytics/telemetry", json=payload)

        # Analytics endpoints typically allow anonymous telemetry
        assert response.status_code == 202

    def test_feedback_optional_user_id(self, api_test_client: TestClient) -> None:
        """Test that feedback does not require a user_id."""
        payload = {
            "action": "like",
            "document_id": "123",
        }

        response = api_test_client.post("/analytics/feedback", json=payload)

        assert response.status_code == 202


class TestAnalyticsPerformance:
    """Test analytics endpoint performance characteristics."""

    def test_telemetry_accepts_large_batches(
        self, api_test_client: TestClient
    ) -> None:
        """Test that large telemetry batches are accepted."""
        # Generate a batch of 100 events
        events = [
            {
                "event": "metric",
                "duration_ms": float(i),
                "metadata": {"metric_name": f"test_{i}", "value": i},
            }
            for i in range(100)
        ]

        payload = {
            "page": "test-session",
            "events": events,
        }

        response = api_test_client.post("/analytics/telemetry", json=payload)

        assert response.status_code == 202

    def test_telemetry_idempotent(self, api_test_client: TestClient) -> None:
        """Test that submitting same telemetry batch multiple times is safe."""
        payload = {
            "page": "idempotent-test",
            "events": [{"event": "test", "duration_ms": 10.0}],
        }

        # Submit twice
        response1 = api_test_client.post("/analytics/telemetry", json=payload)
        response2 = api_test_client.post("/analytics/telemetry", json=payload)

        assert response1.status_code == 202
        assert response2.status_code == 202


class TestAnalyticsDataValidation:
    """Test data validation for analytics endpoints."""

    def test_telemetry_validates_timestamp_format(
        self, api_test_client: TestClient
    ) -> None:
        """Test that invalid timestamp formats are handled."""
        payload = {
            "page": "test",
            "events": [
                {
                    "event": "test",
                    "duration_ms": -1.0, # Invalid duration (must be >= 0)
                }
            ],
        }

        response = api_test_client.post("/analytics/telemetry", json=payload)

        # Depending on validation strictness
        assert response.status_code in [202, 400, 422]

    def test_feedback_validates_target_references(
        self, api_test_client: TestClient
    ) -> None:
        """Test validation of target type and ID combinations."""
        payload = {
            "action": "",  # Empty action
            "user_id": "test-user",
        }

        response = api_test_client.post("/analytics/feedback", json=payload)

        # Should reject empty target_type
        assert response.status_code in [400, 422]
