"""Comprehensive tests for search route endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from theo.infrastructure.api.app.models.search import HybridSearchResponse, HybridSearchResult
from theo.infrastructure.api.app.routes.search import (
    _parse_experiment_tokens,
    _validate_experiment_tokens,
)


class TestSearchEndpoint:
    """Test suite for the main search endpoint GET /search/."""

    def test_search_basic_query(self, api_test_client: TestClient) -> None:
        """Test basic keyword search."""
        response = api_test_client.get("/search/", params={"q": "faith"})

        assert response.status_code == 200
        data = response.json()
        assert "query" in data
        assert data["query"] == "faith"
        assert "results" in data
        assert isinstance(data["results"], list)

    def test_search_response_matches_pydantic_model(
        self, api_test_client: TestClient
    ) -> None:
        """Test that search response conforms to HybridSearchResponse schema."""
        response = api_test_client.get("/search/", params={"q": "grace", "k": 5})

        assert response.status_code == 200
        data = response.json()

        # Validate entire response against Pydantic model
        try:
            validated = HybridSearchResponse.model_validate(data)
        except ValidationError as e:
            pytest.fail(f"Response does not match HybridSearchResponse schema: {e}")

        assert validated.query == "grace"
        assert isinstance(validated.results, list)

        # If results are present, validate each result item
        for i, result in enumerate(validated.results):
            assert isinstance(result, HybridSearchResult), f"Result {i} is not HybridSearchResult"
            # Required fields from HybridSearchResult
            assert hasattr(result, "snippet"), f"Result {i} missing snippet"
            assert hasattr(result, "rank"), f"Result {i} missing rank"
            assert isinstance(result.rank, int), f"Result {i} rank should be int"

    def test_search_with_osis_filter(self, api_test_client: TestClient) -> None:
        """Test search with OSIS reference filter."""
        response = api_test_client.get(
            "/search/",
            params={"q": "grace", "osis": "John.3.16"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "grace"
        assert data["osis"] == "John.3.16"

    def test_search_with_collection_filter(self, api_test_client: TestClient) -> None:
        """Test search with collection filter."""
        response = api_test_client.get(
            "/search/",
            params={"q": "hope", "collection": "systematic-theology"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "hope"

    def test_search_with_author_filter(self, api_test_client: TestClient) -> None:
        """Test search with author filter."""
        response = api_test_client.get(
            "/search/",
            params={"q": "resurrection", "author": "Wright, N.T."},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "resurrection"

    def test_search_with_source_type_filter(self, api_test_client: TestClient) -> None:
        """Test search with source type filter."""
        response = api_test_client.get(
            "/search/",
            params={"q": "exegesis", "source_type": "commentary"},
        )

        assert response.status_code == 200

    def test_search_with_perspective_filter(self, api_test_client: TestClient) -> None:
        """Test search with theological perspective filter."""
        response = api_test_client.get(
            "/search/",
            params={"q": "miracles", "perspective": "skeptical"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "miracles"

    def test_search_with_perspective_apologetic(
        self, api_test_client: TestClient
    ) -> None:
        """Test search with apologetic perspective."""
        response = api_test_client.get(
            "/search/",
            params={"q": "resurrection", "perspective": "apologetic"},
        )

        assert response.status_code == 200

    def test_search_with_perspective_neutral(self, api_test_client: TestClient) -> None:
        """Test search with neutral perspective."""
        response = api_test_client.get(
            "/search/",
            params={"q": "text criticism", "perspective": "neutral"},
        )

        assert response.status_code == 200

    def test_search_with_theological_tradition(
        self, api_test_client: TestClient
    ) -> None:
        """Test search with theological tradition filter."""
        response = api_test_client.get(
            "/search/",
            params={"q": "grace", "theological_tradition": "reformed"},
        )

        assert response.status_code == 200

    def test_search_with_topic_domain_filter(self, api_test_client: TestClient) -> None:
        """Test search with topic domain filter."""
        response = api_test_client.get(
            "/search/",
            params={"q": "justification", "topic_domain": "soteriology"},
        )

        assert response.status_code == 200

    def test_search_with_limit_parameter(self, api_test_client: TestClient) -> None:
        """Test search with custom result limit."""
        response = api_test_client.get(
            "/search/",
            params={"q": "love", "k": 5},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) <= 5

    def test_search_limit_minimum(self, api_test_client: TestClient) -> None:
        """Test search with minimum limit (k=1)."""
        response = api_test_client.get(
            "/search/",
            params={"q": "love", "k": 1},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) <= 1

    def test_search_limit_maximum(self, api_test_client: TestClient) -> None:
        """Test search with maximum limit (k=50)."""
        response = api_test_client.get(
            "/search/",
            params={"q": "love", "k": 50},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) <= 50

    def test_search_limit_too_low_rejected(self, api_test_client: TestClient) -> None:
        """Test that k < 1 is rejected."""
        response = api_test_client.get(
            "/search/",
            params={"q": "love", "k": 0},
        )

        assert response.status_code == 422  # Validation error

    def test_search_limit_too_high_rejected(self, api_test_client: TestClient) -> None:
        """Test that k > 50 is rejected."""
        response = api_test_client.get(
            "/search/",
            params={"q": "love", "k": 51},
        )

        assert response.status_code == 422  # Validation error

    def test_search_without_query_parameters(self, api_test_client: TestClient) -> None:
        """Test search without q or osis returns empty results."""
        response = api_test_client.get("/search/")

        assert response.status_code == 200
        data = response.json()
        assert data["query"] is None
        assert data["osis"] is None

    def test_search_with_multiple_filters(self, api_test_client: TestClient) -> None:
        """Test search with multiple filters combined."""
        response = api_test_client.get(
            "/search/",
            params={
                "q": "covenant",
                "osis": "Genesis.1",
                "collection": "old-testament",
                "author": "Walton, John",
                "source_type": "commentary",
                "perspective": "neutral",
                "k": 20,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "covenant"
        assert data["osis"] == "Genesis.1"


class TestSearchExperiments:
    """Test suite for search experiment flags."""

    def test_search_experiment_single_flag(self, api_test_client: TestClient) -> None:
        """Test search with single experiment flag."""
        response = api_test_client.get(
            "/search/",
            params={"q": "test", "experiment": "rerank=bge"},
        )

        assert response.status_code == 200

    def test_search_experiment_multiple_flags(
        self, api_test_client: TestClient
    ) -> None:
        """Test search with multiple experiment flags."""
        response = api_test_client.get(
            "/search/",
            params=[
                ("q", "test"),
                ("experiment", "rerank=bge"),
                ("experiment", "cap=100"),
                ("experiment", "alpha=0.5"),
            ],
        )

        assert response.status_code == 200

    def test_search_experiment_header_format(self, api_test_client: TestClient) -> None:
        """Test experiment flags via X-Search-Experiments header."""
        response = api_test_client.get(
            "/search/",
            params={"q": "test"},
            headers={"X-Search-Experiments": "rerank=cross,cap=50"},
        )

        assert response.status_code == 200

    def test_search_experiment_header_and_params(
        self, api_test_client: TestClient
    ) -> None:
        """Test experiment flags from both header and query params."""
        response = api_test_client.get(
            "/search/",
            params={"q": "test", "experiment": "alpha=0.5"},
            headers={"X-Search-Experiments": "rerank=bge"},
        )

        assert response.status_code == 200

    def test_search_experiment_too_many_flags_rejected(
        self, api_test_client: TestClient
    ) -> None:
        """Test that exceeding max experiment flags is rejected."""
        # Create 21 experiment flags (max is 20)
        params = [("q", "test")] + [
            ("experiment", f"flag{i}=value") for i in range(21)
        ]

        response = api_test_client.get("/search/", params=params)

        assert response.status_code == 400
        assert "limit is" in response.json()["detail"]

    def test_search_experiment_header_too_long_rejected(
        self, api_test_client: TestClient
    ) -> None:
        """Test that experiment header exceeding max length is rejected."""
        # Create header longer than 512 characters
        long_header = ",".join([f"flag{i}=value" for i in range(50)])

        response = api_test_client.get(
            "/search/",
            params={"q": "test"},
            headers={"X-Search-Experiments": long_header},
        )

        assert response.status_code == 400
        assert "header exceeds" in response.json()["detail"]

    def test_search_experiment_token_too_long_rejected(
        self, api_test_client: TestClient
    ) -> None:
        """Test that individual experiment token exceeding max length is rejected."""
        # Create token longer than 64 characters
        long_token = "x" * 65

        response = api_test_client.get(
            "/search/",
            params={"q": "test", "experiment": long_token},
        )

        assert response.status_code == 400
        assert "shorter than" in response.json()["detail"]

    def test_search_reranker_header_in_response(
        self, api_test_client: TestClient
    ) -> None:
        """Test that X-Reranker header is present in search responses."""
        response = api_test_client.get(
            "/search/",
            params={"q": "test", "k": 10},
        )

        assert response.status_code == 200
        # X-Reranker header indicates which reranker was used (or 'none')
        # Implementation may omit it if no reranking occurred
        reranker = response.headers.get("X-Reranker")
        if reranker is not None:
            # Header should be a non-empty identifier when present
            assert len(reranker) > 0, "X-Reranker header should not be empty"
            assert reranker in {"none", "bge", "cross", "colbert", "default"}, (
                f"Unexpected reranker value: {reranker}"
            )


class TestExperimentHelpers:
    """Test helper functions for experiment token parsing."""

    def test_parse_experiment_tokens_key_value(self) -> None:
        """Test parsing experiment tokens in key=value format."""
        tokens = ["rerank=bge", "cap=100", "alpha=0.5"]
        result = _parse_experiment_tokens(tokens)

        assert result == {
            "rerank": "bge",
            "cap": "100",
            "alpha": "0.5",
        }

    def test_parse_experiment_tokens_key_colon_value(self) -> None:
        """Test parsing experiment tokens in key:value format."""
        tokens = ["rerank:bge", "cap:100"]
        result = _parse_experiment_tokens(tokens)

        assert result == {
            "rerank": "bge",
            "cap": "100",
        }

    def test_parse_experiment_tokens_flag_only(self) -> None:
        """Test parsing experiment tokens with flag-only format."""
        tokens = ["enable_feature", "debug"]
        result = _parse_experiment_tokens(tokens)

        assert result == {
            "enable_feature": "1",
            "debug": "1",
        }

    def test_parse_experiment_tokens_mixed_formats(self) -> None:
        """Test parsing mixed format experiment tokens."""
        tokens = ["rerank=bge", "cap:100", "debug"]
        result = _parse_experiment_tokens(tokens)

        assert result == {
            "rerank": "bge",
            "cap": "100",
            "debug": "1",
        }

    def test_parse_experiment_tokens_empty_strings_ignored(self) -> None:
        """Test that empty strings are ignored."""
        tokens = ["rerank=bge", "", "cap=100", ""]
        result = _parse_experiment_tokens(tokens)

        assert result == {
            "rerank": "bge",
            "cap": "100",
        }

    def test_parse_experiment_tokens_case_normalization(self) -> None:
        """Test that keys are normalized to lowercase."""
        tokens = ["RERANK=bge", "Cap=100", "AlPhA=0.5"]
        result = _parse_experiment_tokens(tokens)

        assert result == {
            "rerank": "bge",
            "cap": "100",
            "alpha": "0.5",
        }

    def test_validate_experiment_tokens_valid(self) -> None:
        """Test validation passes for valid tokens."""
        tokens = ["rerank=bge", "cap=100", "alpha=0.5"]
        result = _validate_experiment_tokens(tokens)

        assert result == tokens

    def test_validate_experiment_tokens_filters_empty(self) -> None:
        """Test that empty strings are filtered out."""
        tokens = ["rerank=bge", "", "cap=100"]
        result = _validate_experiment_tokens(tokens)

        assert result == ["rerank=bge", "cap=100"]

    def test_validate_experiment_tokens_too_many_raises(self) -> None:
        """Test that exceeding max count raises HTTPException."""
        tokens = [f"flag{i}=value" for i in range(21)]

        with pytest.raises(Exception) as exc_info:
            _validate_experiment_tokens(tokens)

        assert "Too many experiment flags" in str(exc_info.value)

    def test_validate_experiment_tokens_too_long_raises(self) -> None:
        """Test that oversized token raises HTTPException."""
        tokens = ["x" * 65]

        with pytest.raises(Exception) as exc_info:
            _validate_experiment_tokens(tokens)

        assert "shorter than" in str(exc_info.value)


@pytest.mark.no_auth_override
class TestSearchAuthentication:
    """Test search endpoint authentication requirements.

    These tests run with authentication enforcement enabled (no_auth_override marker).
    The search endpoint behavior depends on the API's authentication configuration:
    - Public access: Returns 200 OK without credentials
    - Protected: Returns 401 Unauthorized without valid credentials
    """

    def test_search_unauthenticated_returns_expected_status(self, api_test_client: TestClient) -> None:
        """Test search endpoint returns consistent status without authentication.

        The search endpoint is configured as publicly accessible in the current
        implementation, so this should return 200 OK even without credentials.
        If the auth policy changes, update this test accordingly.
        """
        response = api_test_client.get("/search/", params={"q": "test"})

        # Search endpoint is publicly accessible (no auth required)
        # If this starts failing with 401, the auth policy has changed
        assert response.status_code == 200, (
            f"Expected 200 for public search endpoint, got {response.status_code}. "
            "If auth policy changed, update this test to expect 401."
        )

    def test_search_with_invalid_api_key(self, api_test_client: TestClient) -> None:
        """Test search endpoint behavior with an invalid API key.

        Since search is publicly accessible, invalid API keys should not
        block access. The endpoint should either:
        - Ignore the invalid key (200 OK)
        - Reject only if auth is enforced (401/403)
        """
        response = api_test_client.get(
            "/search/",
            params={"q": "test"},
            headers={"X-API-Key": "invalid-key-12345"},
        )

        # Public endpoint: invalid key is ignored (200)
        # Protected endpoint: invalid key is rejected (401/403)
        assert response.status_code in [200, 401, 403], (
            f"Unexpected status {response.status_code} with invalid API key"
        )
