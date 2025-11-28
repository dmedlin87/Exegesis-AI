"""Tests for the discoveries graph endpoint."""

from unittest.mock import Mock

import pytest

from exegesis.application.dtos import DiscoveryDTO
from exegesis.infrastructure.api.app.models.discoveries import (
    DiscoveryGraphResponse,
    GraphLink,
    GraphNode,
)


def test_graph_response_model():
    """Test that the graph response model is correctly defined."""
    node = GraphNode(
        id="1",
        type="discovery",
        label="Test Discovery",
        discoveryType="anomaly",
        confidence=0.85,
        viewed=False,
    )

    link = GraphLink(
        source="1",
        target="doc_123",
        type="references",
    )

    response = DiscoveryGraphResponse(
        nodes=[node],
        links=[link],
    )

    assert len(response.nodes) == 1
    assert len(response.links) == 1
    assert response.nodes[0].id == "1"
    assert response.nodes[0].type == "discovery"
    assert response.links[0].source == "1"


def test_graph_node_evidence_type():
    """Test that evidence nodes can be created."""
    node = GraphNode(
        id="doc_123",
        type="evidence",
        label="Test Document",
    )

    assert node.type == "evidence"
    assert node.discoveryType is None
    assert node.confidence is None
    assert node.viewed is None


def test_graph_response_empty():
    """Test that an empty graph response is valid."""
    response = DiscoveryGraphResponse(
        nodes=[],
        links=[],
    )

    assert len(response.nodes) == 0
    assert len(response.links) == 0


def test_graph_node_all_discovery_types():
    """Test nodes for all discovery types."""
    discovery_types = ["anomaly", "contradiction", "gap", "connection", "pattern", "trend"]

    for disc_type in discovery_types:
        node = GraphNode(
            id=f"disc_{disc_type}",
            type="discovery",
            label=f"Test {disc_type}",
            discoveryType=disc_type,
            confidence=0.9,
            viewed=True,
        )

        assert node.discoveryType == disc_type
        assert node.type == "discovery"


def test_graph_link_types():
    """Test different link types."""
    link_types = ["references", "contradicts", "connects"]

    for link_type in link_types:
        link = GraphLink(
            source="1",
            target="2",
            type=link_type,
        )

        assert link.type == link_type


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
