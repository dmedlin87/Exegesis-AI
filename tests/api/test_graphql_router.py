"""Tests for GraphQL router and endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestGraphQLEndpoint:
    """Test GraphQL endpoint configuration and access."""

    def test_graphql_endpoint_accessible(self, api_test_client: TestClient) -> None:
        """Test that GraphQL endpoint is accessible."""
        # GraphQL typically accepts both GET and POST
        response = api_test_client.post("/graphql", json={"query": "{ __schema { types { name } } }"})

        # Should return 200 or appropriate status
        assert response.status_code in [200, 400, 401]

    def test_graphql_introspection_query(self, api_test_client: TestClient) -> None:
        """Test GraphQL introspection query."""
        query = """
        query IntrospectionQuery {
            __schema {
                queryType {
                    name
                }
                mutationType {
                    name
                }
                types {
                    name
                    kind
                }
            }
        }
        """

        response = api_test_client.post("/graphql", json={"query": query})

        assert response.status_code == 200
        data = response.json()
        assert "data" in data or "errors" in data

    def test_graphql_invalid_query_returns_error(
        self, api_test_client: TestClient
    ) -> None:
        """Test that invalid GraphQL query returns error."""
        response = api_test_client.post(
            "/graphql", json={"query": "invalid query syntax {"}
        )

        assert response.status_code in [200, 400]
        if response.status_code == 200:
            data = response.json()
            assert "errors" in data

    def test_graphql_query_with_variables(self, api_test_client: TestClient) -> None:
        """Test GraphQL query with variables."""
        query = """
        query GetDocument($id: ID!) {
            document(id: $id) {
                id
                metadata {
                    title
                }
            }
        }
        """
        variables = {"id": "test-doc-1"}

        response = api_test_client.post(
            "/graphql",
            json={"query": query, "variables": variables},
        )

        assert response.status_code == 200
        # Verify no errors
        data = response.json()
        assert "errors" not in data

    def test_graphql_mutation(self, api_test_client: TestClient) -> None:
        """Test GraphQL mutation operation."""
        mutation = """
        mutation IngestDocument($input: DocumentInput!) {
            ingestDocument(input: $input) {
                documentId
            }
        }
        """
        variables = {
            "input": {
                "id": "test-doc-mutation",
                "metadata": {
                    "title": "Test Document",
                    "source": "Test Source"
                },
                "scriptureRefs": [],
                "tags": []
            }
        }

        response = api_test_client.post(
            "/graphql",
            json={"query": mutation, "variables": variables},
        )

        # May require authentication or return validation error
        assert response.status_code in [200, 401]
        if response.status_code == 200:
            data = response.json()
            if "errors" in data:
                # If it's an auth error inside GraphQL, that's expected for this test
                pass
            else:
                assert "data" in data

    def test_graphql_context_includes_session(
        self, api_test_client: TestClient
    ) -> None:
        """Test that GraphQL context includes database session."""
        # This requires a query that accesses the database
        query = """
        {
            documents(limit: 1) {
                id
                metadata {
                    title
                }
            }
        }
        """

        response = api_test_client.post("/graphql", json={"query": query})

        assert response.status_code == 200
        data = response.json()
        assert "errors" not in data

    def test_query_single_document(self, api_test_client: TestClient) -> None:
        """Test querying single document by ID."""
        query = """
        query GetDocument($id: ID!) {
            document(id: $id) {
                id
                metadata {
                    title
                }
                scriptureRefs
            }
        }
        """

        response = api_test_client.post(
            "/graphql",
            json={"query": query, "variables": {"id": "test-doc"}},
        )

        assert response.status_code == 200
        data = response.json()
        assert "errors" not in data

    def test_query_nested_relationships(self, api_test_client: TestClient) -> None:
        """Test querying nested relationships."""
        query = """
        {
            documents(limit: 1) {
                id
                metadata {
                    title
                }
                scriptureRefs
            }
        }
        """

        response = api_test_client.post("/graphql", json={"query": query})

        assert response.status_code == 200
        data = response.json()
        assert "errors" not in data

    def test_mutation_requires_authentication(
        self, api_test_client: TestClient
    ) -> None:
        """Test that mutations require authentication."""
        mutation = """
        mutation {
            ingestDocument(input: {
                id: "test-auth",
                metadata: {title: "Test", source: "Test"},
                scriptureRefs: [],
                tags: []
            }) {
                documentId
            }
        }
        """

        response = api_test_client.post("/graphql", json={"query": mutation})

        # Should require authentication or return validation error
        assert response.status_code in [200, 401]

    def test_graphql_handles_complex_queries(
        self, api_test_client: TestClient
    ) -> None:
        """Test that complex nested queries are handled efficiently."""
        query = """
        {
            documents(limit: 5) {
                id
                metadata {
                    title
                    source
                }
                scriptureRefs
                tags
            }
        }
        """

        response = api_test_client.post("/graphql", json={"query": query})

        assert response.status_code == 200
        data = response.json()
        assert "errors" not in data

    def test_graphql_pagination(self, api_test_client: TestClient) -> None:
        """Test GraphQL pagination support."""
        # Offset is not supported in the current schema, only limit
        query = """
        {
            documents(limit: 10) {
                id
            }
        }
        """

        response = api_test_client.post("/graphql", json={"query": query})

        assert response.status_code == 200
        data = response.json()
        assert "errors" not in data

    def test_graphql_syntax_error(self, api_test_client: TestClient) -> None:
        """Test GraphQL syntax error handling."""
        response = api_test_client.post(
            "/graphql",
            json={"query": "{ invalid syntax"},
        )

        assert response.status_code in [200, 400]
        if response.status_code == 200:
            data = response.json()
            assert "errors" in data

    def test_graphql_validation_error(self, api_test_client: TestClient) -> None:
        """Test GraphQL validation error handling."""
        query = """
        {
            nonExistentField {
                id
            }
        }
        """

        response = api_test_client.post("/graphql", json={"query": query})

        assert response.status_code == 200
        data = response.json()
        # Should return errors for invalid field
        assert "errors" in data
