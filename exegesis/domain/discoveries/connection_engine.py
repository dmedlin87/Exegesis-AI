"""Connection discovery engine leveraging graph analysis with NetworkX."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Mapping, Sequence

import networkx as nx

from .models import DocumentEmbedding


@dataclass(frozen=True)
class ConnectionDiscovery:
    """A graph-derived relationship between documents."""

    title: str
    description: str
    confidence: float
    relevance_score: float
    metadata: Mapping[str, object] = field(default_factory=dict)


class ConnectionDiscoveryEngine:
    """Analyse shared references to surface strongly connected documents."""

    def __init__(
        self,
        *,
        min_shared_verses: int = 1,
        min_documents: int = 2,
        max_results: int = 10,
    ) -> None:
        if min_shared_verses < 1:
            raise ValueError("min_shared_verses must be at least 1")
        if min_documents < 2:
            raise ValueError("min_documents must be at least 2")
        if max_results < 1:
            raise ValueError("max_results must be positive")
        self.min_shared_verses = int(min_shared_verses)
        self.min_documents = int(min_documents)
        self.max_results = int(max_results)

    def detect(self, documents: Sequence[DocumentEmbedding]) -> list[ConnectionDiscovery]:
        """Return connection discoveries for *documents*.

        Args:
            documents: Sequence of documents with verse references.

        Returns:
            List of connection discoveries sorted by confidence.
        """
        filtered, verse_sets, document_rank = self._filter_documents_with_verses(documents)
        if len(filtered) < self.min_documents:
            return []

        bipartite_graph, document_nodes = self._build_bipartite_graph(filtered, verse_sets)
        if not bipartite_graph.number_of_edges():
            return []

        pruned = self._project_and_prune_graph(bipartite_graph, document_nodes)
        if pruned.number_of_edges() == 0:
            return []

        discoveries = self._extract_discoveries_from_components(
            pruned, bipartite_graph, verse_sets, document_rank
        )
        discoveries.sort(key=lambda item: (item.confidence, item.relevance_score), reverse=True)
        return discoveries[: self.max_results]

    def _filter_documents_with_verses(
        self, documents: Sequence[DocumentEmbedding]
    ) -> tuple[list[DocumentEmbedding], dict[str, set[int]], dict[str, int]]:
        """Filter documents to those with valid verse references.

        Args:
            documents: Input documents to filter.

        Returns:
            Tuple of (filtered_docs, verse_sets_by_doc_id, document_rank).
        """
        verse_sets: dict[str, set[int]] = {}
        filtered: list[DocumentEmbedding] = []
        document_rank: dict[str, int] = {}
        for doc in documents:
            verses = {verse for verse in doc.verse_ids if isinstance(verse, int)}
            if not verses:
                continue
            verse_sets[doc.document_id] = verses
            filtered.append(doc)
            document_rank[doc.document_id] = len(filtered) - 1
        return filtered, verse_sets, document_rank

    def _build_bipartite_graph(
        self,
        filtered: list[DocumentEmbedding],
        verse_sets: dict[str, set[int]],
    ) -> tuple[nx.Graph, list[tuple[str, str]]]:
        """Build a bipartite graph connecting documents to verses.

        Args:
            filtered: Documents with verse references.
            verse_sets: Mapping of document IDs to verse sets.

        Returns:
            Tuple of (bipartite_graph, document_node_list).
        """
        bipartite_graph = nx.Graph()
        document_nodes: list[tuple[str, str]] = []
        for doc in filtered:
            doc_node = ("document", doc.document_id)
            bipartite_graph.add_node(doc_node, bipartite=0, document=doc)
            document_nodes.append(doc_node)
            for verse in verse_sets[doc.document_id]:
                verse_node = ("verse", verse)
                bipartite_graph.add_node(verse_node, bipartite=1, verse=verse)
                bipartite_graph.add_edge(doc_node, verse_node)
        return bipartite_graph, document_nodes

    def _project_and_prune_graph(
        self,
        bipartite_graph: nx.Graph,
        document_nodes: list[tuple[str, str]],
    ) -> nx.Graph:
        """Project bipartite graph and prune edges below threshold.

        Args:
            bipartite_graph: Bipartite document-verse graph.
            document_nodes: List of document node identifiers.

        Returns:
            Pruned graph with only significant edges.
        """
        projected = nx.algorithms.bipartite.weighted_projected_graph(
            bipartite_graph, document_nodes
        )
        pruned = nx.Graph()
        for node, data in projected.nodes(data=True):
            pruned.add_node(node, **data)

        for source_node, target_node, edge_data in projected.edges(data=True):
            weight = int(edge_data.get("weight", 0))
            if weight >= self.min_shared_verses:
                pruned.add_edge(source_node, target_node, weight=weight)
        return pruned

    def _extract_discoveries_from_components(
        self,
        pruned: nx.Graph,
        bipartite_graph: nx.Graph,
        verse_sets: dict[str, set[int]],
        document_rank: dict[str, int],
    ) -> list[ConnectionDiscovery]:
        """Process connected components into discoveries.

        Args:
            pruned: Pruned document relationship graph.
            bipartite_graph: Original bipartite graph with document data.
            verse_sets: Mapping of document IDs to verse sets.
            document_rank: Ordering of documents for sorting.

        Returns:
            List of connection discoveries from valid components.
        """
        discoveries: list[ConnectionDiscovery] = []
        for component_nodes in nx.connected_components(pruned):
            discovery = self._process_component(
                component_nodes, pruned, bipartite_graph, verse_sets, document_rank
            )
            if discovery is not None:
                discoveries.append(discovery)
        return discoveries

    def _process_component(
        self,
        component_nodes: set,
        pruned: nx.Graph,
        bipartite_graph: nx.Graph,
        verse_sets: dict[str, set[int]],
        document_rank: dict[str, int],
    ) -> ConnectionDiscovery | None:
        """Process a single connected component into a discovery.

        Args:
            component_nodes: Set of nodes in the component.
            pruned: Pruned document relationship graph.
            bipartite_graph: Original bipartite graph with document data.
            verse_sets: Mapping of document IDs to verse sets.
            document_rank: Ordering of documents for sorting.

        Returns:
            ConnectionDiscovery if component is valid, None otherwise.
        """
        if len(component_nodes) < self.min_documents:
            return None

        subgraph = pruned.subgraph(component_nodes)
        docs = sorted(
            (
                bipartite_graph.nodes[node]["document"]
                for node in component_nodes
                if node in bipartite_graph
            ),
            key=lambda doc: document_rank.get(doc.document_id, 0),
        )
        if len(docs) < self.min_documents:
            return None

        shared_verses, shared_topics = self._compute_shared_content(docs, verse_sets)
        if not shared_verses:
            return None

        edges_payload, edge_weights = self._build_edge_payload(
            subgraph, bipartite_graph, verse_sets
        )
        if not edge_weights:
            return None

        return self._create_discovery(
            docs, shared_verses, shared_topics, edges_payload, edge_weights, subgraph
        )

    def _compute_shared_content(
        self,
        docs: list[DocumentEmbedding],
        verse_sets: dict[str, set[int]],
    ) -> tuple[list[int], list[str]]:
        """Compute shared verses and topics across documents.

        Args:
            docs: List of documents to analyze.
            verse_sets: Mapping of document IDs to verse sets.

        Returns:
            Tuple of (shared_verses, shared_topics).
        """
        verse_counter: Counter[int] = Counter()
        topic_counter: Counter[str] = Counter()
        for doc in docs:
            verse_counter.update(verse_sets.get(doc.document_id, set()))
            topic_counter.update(
                self._normalise_topic(topic)
                for topic in doc.topics
                if isinstance(topic, str)
            )

        shared_verses = sorted(
            verse for verse, count in verse_counter.items() if count >= 2
        )
        shared_topics = [
            topic for topic, count in topic_counter.items() if count >= 2 and topic
        ][:5]
        return shared_verses, shared_topics

    def _build_edge_payload(
        self,
        subgraph: nx.Graph,
        bipartite_graph: nx.Graph,
        verse_sets: dict[str, set[int]],
    ) -> tuple[list[dict[str, object]], list[int]]:
        """Build edge payload data for the connection metadata.

        Args:
            subgraph: Subgraph of the component.
            bipartite_graph: Original bipartite graph with document data.
            verse_sets: Mapping of document IDs to verse sets.

        Returns:
            Tuple of (edges_payload, edge_weights).
        """
        edges_payload: list[dict[str, object]] = []
        edge_weights: list[int] = []
        for source_node, target_node, edge_data in subgraph.edges(data=True):
            doc_a = bipartite_graph.nodes[source_node]["document"]
            doc_b = bipartite_graph.nodes[target_node]["document"]
            shared = sorted(
                verse_sets[doc_a.document_id] & verse_sets[doc_b.document_id]
            )
            weight = int(edge_data.get("weight", len(shared)))
            edge_weights.append(weight)
            edges_payload.append(
                {
                    "documentA": doc_a.document_id,
                    "documentB": doc_b.document_id,
                    "sharedVerses": shared,
                    "sharedVerseCount": len(shared),
                    "weight": weight,
                }
            )
        return edges_payload, edge_weights

    def _create_discovery(
        self,
        docs: list[DocumentEmbedding],
        shared_verses: list[int],
        shared_topics: list[str],
        edges_payload: list[dict[str, object]],
        edge_weights: list[int],
        subgraph: nx.Graph,
    ) -> ConnectionDiscovery:
        """Create a ConnectionDiscovery from computed data.

        Args:
            docs: Documents in the connection.
            shared_verses: Verses shared across documents.
            shared_topics: Topics shared across documents.
            edges_payload: Edge connection data.
            edge_weights: Weights of each edge.
            subgraph: Graph subgraph for density calculation.

        Returns:
            Constructed ConnectionDiscovery instance.
        """
        max_shared = max(edge_weights)
        density = nx.density(subgraph)
        confidence = min(0.95, round(0.45 + 0.1 * max_shared + 0.25 * density, 4))
        relevance = min(
            0.9,
            round(
                0.35 + 0.05 * len(docs) + 0.05 * len(shared_verses) + 0.05 * len(shared_topics),
                4,
            ),
        )

        title = self._generate_title(docs)
        description = self._generate_description(docs, shared_verses, shared_topics)
        metadata = self._build_metadata(docs, shared_verses, shared_topics, edges_payload, density, max_shared)

        return ConnectionDiscovery(
            title=title,
            description=description,
            confidence=confidence,
            relevance_score=relevance,
            metadata=metadata,
        )

    def _generate_title(self, docs: list[DocumentEmbedding]) -> str:
        """Generate a title for the connection discovery.

        Args:
            docs: Documents in the connection.

        Returns:
            Human-readable title string.
        """
        cleaned_titles = [
            (doc.title.strip() if isinstance(doc.title, str) else "") for doc in docs
        ]
        fallbacks = [doc.document_id for doc in docs]
        resolved_titles = [
            title or fallback for title, fallback in zip(cleaned_titles, fallbacks, strict=True)
        ]
        if len(docs) == 2:
            return f"Connection between {resolved_titles[0]} and {resolved_titles[1]}"
        return f"Connection cluster spanning {len(docs)} documents"

    def _generate_description(
        self, docs: list[DocumentEmbedding], shared_verses: list[int], shared_topics: list[str]
    ) -> str:
        """Generate a description for the connection discovery.

        Args:
            docs: Documents in the connection.
            shared_verses: Verses shared across documents.
            shared_topics: Topics shared across documents.

        Returns:
            Human-readable description string.
        """
        parts = [f"Detected a network of {len(docs)} documents linked by shared verses."]
        shared_verse_preview = ", ".join(str(verse) for verse in shared_verses[:5])
        if shared_verse_preview:
            parts.append(f"Key shared verses include {shared_verse_preview}.")
        if shared_topics:
            parts.append(f"Common themes: {', '.join(topic.title() for topic in shared_topics)}")
        return " ".join(parts)

    def _build_metadata(
        self,
        docs: list[DocumentEmbedding],
        shared_verses: list[int],
        shared_topics: list[str],
        edges_payload: list[dict[str, object]],
        density: float,
        max_shared: int,
    ) -> dict[str, object]:
        """Build metadata dictionary for the connection discovery.

        Args:
            docs: Documents in the connection.
            shared_verses: Verses shared across documents.
            shared_topics: Topics shared across documents.
            edges_payload: Edge connection data.
            density: Graph density value.
            max_shared: Maximum shared verse count.

        Returns:
            Metadata dictionary.
        """
        return {
            "relatedDocuments": [doc.document_id for doc in docs],
            "relatedVerses": shared_verses,
            "relatedTopics": shared_topics,
            "connectionData": {
                "edgeList": edges_payload,
                "graphDensity": round(density, 4),
                "sharedVerseCount": len(shared_verses),
                "maxSharedPerEdge": max_shared,
            },
        }

    @staticmethod
    def _normalise_topic(topic: str) -> str:
        """Normalise a topic string for comparison.

        Args:
            topic: Topic string to normalise.

        Returns:
            Lowercase, stripped topic string.
        """
        return topic.strip().lower()


__all__ = ["ConnectionDiscovery", "ConnectionDiscoveryEngine"]

