from __future__ import annotations

from sqlalchemy.orm import Session

from .topics import TopicDigest, load_topic_digest as _load_topic_digest

class AnalyticsService:
    """Service for analytics operations."""

    def __init__(self, session: Session):
        self._session = session

def load_topic_digest(session: Session) -> TopicDigest | None:
    return _load_topic_digest(session)
