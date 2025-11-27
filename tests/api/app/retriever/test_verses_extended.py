from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
from typing import Any

import pytest
from sqlalchemy.orm import Session
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from exegesis.infrastructure.api.app.models.verses import VerseMentionsFilters  # noqa: E402
from exegesis.infrastructure.api.app.retrieval.retriever import verses as verses_module  # noqa: E402
from exegesis.infrastructure.api.app.retrieval.retriever.verses import (  # noqa: E402
    get_mentions_for_osis,
    get_verse_timeline,
)


def _make_mock_session() -> Session:
    return MagicMock(spec=Session)


def test_malformed_osis_returns_empty() -> None:
    session = _make_mock_session()

    mentions = get_mentions_for_osis(session=session, osis="Invalid.Ref.1")
    timeline = get_verse_timeline(session=session, osis="Invalid.Ref.1")

    assert mentions == []
    assert timeline.osis == "Invalid.Ref.1"
    assert timeline.buckets == []
    assert timeline.total_mentions == 0

    session.get_bind.assert_not_called()
    assert not session.execute.called


def test_author_filter_no_match() -> None:
    session = _make_mock_session()

    with (
        patch.object(verses_module, "_resolve_query_ids", return_value=[1, 2]) as resolve_mock,
        patch.object(verses_module, "_document_ids_for_author", return_value=[])
        as author_ids_mock,
    ):
        filters = VerseMentionsFilters(author="Nonexistent Author")

        response = get_verse_timeline(session=session, osis="John.3.16", filters=filters)

    resolve_mock.assert_called_once_with("John.3.16")
    author_ids_mock.assert_called_once()

    assert response.osis == "John.3.16"
    assert response.buckets == []
    assert response.total_mentions == 0
    assert not session.execute.called


def test_python_timeline_fallback() -> None:
    session = _make_mock_session()

    class _EmptyAggResult:
        def all(self) -> list[Any]:
            return []

    session.execute.return_value = _EmptyAggResult()

    called = {"python": False}

    real_timeline_from_passages = verses_module._timeline_from_passages

    def _fake_python_timeline(
        *,
        session: Session,
        filters: VerseMentionsFilters | None,
        window: str,
        limit: int | None,
        range_start: int,
        range_end: int,
        allowed_doc_ids: list[str] | None,
    ):
        called["python"] = True

        from exegesis.infrastructure.api.app.persistence_models import Document, Passage

        document = Document(
            id="doc-python",
            title="Python Timeline",
            source_type="pdf",
            pub_date=date(2024, 1, 15),
        )
        passage = Passage(
            id="passage-python",
            document_id=document.id,
            text="Python fallback",
            osis_ref="John.3.16",
            osis_start_verse_id=None,
            osis_end_verse_id=None,
        )
        passage.document = document

        passages = [passage]
        buckets, total = real_timeline_from_passages(passages, filters, window, limit)
        return buckets, total

    with (
        patch.object(verses_module, "_resolve_query_ids", return_value=[100, 100]),
        patch.object(verses_module, "_legacy_timeline", return_value=([], 0)),
        patch.object(
            verses_module,
            "_python_timeline",
            side_effect=lambda **kwargs: _fake_python_timeline(**kwargs),
        ),
    ):
        filters = VerseMentionsFilters()
        response = get_verse_timeline(
            session=session,
            osis="John.3.16",
            window="month",
            filters=filters,
        )

    assert called["python"] is True

    assert response.osis == "John.3.16"
    assert response.window == "month"
    assert response.total_mentions == 1
    assert len(response.buckets) == 1

    bucket = response.buckets[0]
    assert bucket.document_ids == ["doc-python"]
    assert bucket.sample_passage_ids == ["passage-python"]
    assert bucket.label == "2024-01"
