from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Iterable

from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from exegesis.infrastructure.api.app.persistence_models import Document, Passage  # noqa: E402
from exegesis.infrastructure.api.app.retrieval.retriever import hybrid as hybrid_module  # noqa: E402
from exegesis.infrastructure.api.app.retrieval.retriever.hybrid import (  # noqa: E402
    HybridSearchFilters,
    HybridSearchRequest,
)


def _make_session() -> Session:
    return MagicMock(spec=Session)


def _make_passage(
    *,
    passage_id: str,
    document_id: str,
    text: str = "",
    osis_ref: str | None = None,
    meta: dict[str, Any] | None = None,
) -> Passage:
    passage = Passage(
        id=passage_id,
        document_id=document_id,
        text=text,
        osis_ref=osis_ref,
    )
    passage.meta = meta or {}
    return passage


def _make_document(*, doc_id: str, title: str = "Doc", theological_tradition: str | None = None,
                   topic_domains: list[str] | None = None) -> Document:
    document = Document(id=doc_id, title=title, source_type="pdf")
    document.theological_tradition = theological_tradition
    document.topic_domains = topic_domains
    return document


def test_fallback_search_filtering() -> None:
    session = _make_session()

    matching_doc = _make_document(doc_id="doc-osis", title="OSIS Doc")
    non_matching_doc = _make_document(doc_id="doc-other", title="Other Doc")

    passage_with_osis = _make_passage(
        passage_id="p-osis",
        document_id=matching_doc.id,
        text="Some text",
        osis_ref="John.3.16",
    )
    passage_with_tei = _make_passage(
        passage_id="p-tei",
        document_id=non_matching_doc.id,
        text="",
        meta={"tei_search_blob": "grace"},
    )

    rows = [
        (passage_with_osis, matching_doc),
        (passage_with_tei, non_matching_doc),
    ]

    class _ExecResult:
        def __init__(self, payload: list[tuple[Passage, Document]]):
            self._payload = payload

        def all(self) -> list[tuple[Passage, Document]]:
            return self._payload

    with patch.object(hybrid_module, "execute_with_metrics", return_value=_ExecResult(rows)):
        request_osis_only = HybridSearchRequest(
            query=None,
            osis="John.3.16",
            k=5,
            filters=HybridSearchFilters(),
        )
        results_osis = hybrid_module._fallback_search(session=session, request=request_osis_only)

    assert {r.id for r in results_osis} == {"p-osis"}

    with patch.object(hybrid_module, "execute_with_metrics", return_value=_ExecResult(rows)):
        request_query_only = HybridSearchRequest(
            query="grace",
            osis=None,
            k=5,
            filters=HybridSearchFilters(),
        )
        results_query = hybrid_module._fallback_search(session=session, request=request_query_only)

    returned_ids = {r.id for r in results_query}
    assert "p-tei" in returned_ids
    assert "p-osis" not in returned_ids


def test_guardrail_filters() -> None:
    document = _make_document(
        doc_id="doc-1",
        title="Reformed Doc",
        theological_tradition="Reformed",
        topic_domains=["christology"],
    )

    filters_match = HybridSearchFilters(theological_tradition="reformed")
    assert hybrid_module._passes_guardrail_filters(document, filters_match) is True

    filters_mismatch = HybridSearchFilters(theological_tradition="Catholic")
    assert hybrid_module._passes_guardrail_filters(document, filters_mismatch) is False


def test_candidate_scoring_pruning() -> None:
    request_with_query = HybridSearchRequest(
        query="grace",
        osis=None,
        k=5,
        filters=HybridSearchFilters(),
    )
    request_without_query = HybridSearchRequest(
        query=None,
        osis=None,
        k=5,
        filters=HybridSearchFilters(),
    )

    document = _make_document(doc_id="doc-1")
    passage = _make_passage(passage_id="p-1", document_id=document.id, text="")
    candidate = hybrid_module._Candidate(passage=passage, document=document)

    score_with_query = hybrid_module._calculate_candidate_score(
        candidate,
        request_with_query,
        query_tokens=["grace"],
        annotation_notes=[],
    )
    assert score_with_query is None

    candidate_no_query = hybrid_module._Candidate(passage=passage, document=document)
    score_without_query = hybrid_module._calculate_candidate_score(
        candidate_no_query,
        request_without_query,
        query_tokens=[],
        annotation_notes=[],
    )
    assert score_without_query is not None
    assert score_without_query >= 0.1


def test_osis_distance_calculation() -> None:
    passage_same = _make_passage(
        passage_id="p-same",
        document_id="doc-1",
        osis_ref="John.3.16",
        text="",
    )
    distance_same = hybrid_module._osis_distance_value(passage_same, "John.3.16")
    assert distance_same == 0.0

    passage_other = _make_passage(
        passage_id="p-other",
        document_id="doc-1",
        osis_ref="John.3.16",
        text="",
    )
    distance_other = hybrid_module._osis_distance_value(passage_other, "John.3.17")
    assert distance_other is not None
    assert distance_other > 0.0
