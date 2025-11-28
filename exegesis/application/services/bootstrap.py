"""Service-layer bootstrap helpers bridging to the application container."""
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import lru_cache
from typing import Tuple

from exegesis.adapters import AdapterRegistry
from exegesis.adapters.persistence.sqlalchemy_support import (
    Session,
    select,
    load_only,
    selectinload,
)

from exegesis.adapters.persistence.collection_repository import (
    SQLAlchemyCollectionRepository,
)
from exegesis.adapters.persistence.embedding_repository import (
    SQLAlchemyPassageEmbeddingRepository,
)
from exegesis.adapters.persistence.models import Document as DocumentRecord, Passage
from exegesis.adapters.research import (
    SqlAlchemyHypothesisRepositoryFactory,
    SqlAlchemyResearchNoteRepositoryFactory,
)
from exegesis.application.facades.database import get_engine
from exegesis.application.facades.settings import get_settings
from exegesis.application.research import ResearchService
from exegesis.application.retrieval.embeddings import (
    EmbeddingRebuildService,
    LazyEmbeddingBackend,
)
from exegesis.domain import Document, DocumentId, DocumentMetadata

from .container import ApplicationContainer

EMBEDDING_BACKEND_FACTORY_PORT = "embedding_backend_factory"
EMBEDDING_SANITIZE_PORT = "sanitize_passage_text"
EMBEDDING_CACHE_CLEARER_PORT = "clear_embedding_cache"

_adapter_registry_hooks: list[Callable[[AdapterRegistry], None]] = []


def register_adapter_hook(hook: Callable[[AdapterRegistry], None]) -> None:
    """Register a callback invoked after the adapter registry is created."""

    _adapter_registry_hooks.append(hook)


def _run_adapter_hooks(registry: AdapterRegistry) -> None:
    for hook in _adapter_registry_hooks:
        hook(registry)


@contextmanager
def _session_scope(registry: AdapterRegistry) -> Iterator[Session]:
    """Yield a SQLAlchemy session bound to the registry's engine."""

    engine = registry.resolve("engine")
    with Session(engine) as session:
        yield session


@contextmanager
def _maybe_session_scope(
    registry: AdapterRegistry, session: Session | None = None
) -> Iterator[Session]:
    """Yield the provided session or create a new one if None."""
    if session is not None:
        yield session
    else:
        with _session_scope(registry) as new_session:
            yield new_session


def _extract_language(record: DocumentRecord) -> str | None:
    """Derive the document's language from stored metadata."""

    payload = record.bib_json if isinstance(record.bib_json, dict) else {}
    language = payload.get("language") or payload.get("lang")
    return str(language) if isinstance(language, str) and language.strip() else None


def _extract_tags(record: DocumentRecord) -> list[str]:
    """Collect tag metadata from the document record."""

    tags: list[str] = []
    if isinstance(record.topics, list):
        tags.extend(str(item) for item in record.topics if isinstance(item, str) and item)
    elif isinstance(record.topics, dict):
        tags.extend(
            str(value)
            for value in record.topics.values()
            if isinstance(value, str) and value
        )

    payload = record.bib_json if isinstance(record.bib_json, dict) else {}
    extra_tags = payload.get("tags")
    if isinstance(extra_tags, (list, tuple, set)):
        tags.extend(str(item) for item in extra_tags if isinstance(item, str) and item)

    seen: set[str] = set()
    unique: list[str] = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            unique.append(tag)
    return unique


def _extract_scripture_refs(session: Session, record: DocumentRecord) -> tuple[str, ...]:
    """Return ordered scripture references associated with a document."""

    refs: list[str] = []
    seen: set[str] = set()

    payload = record.bib_json if isinstance(record.bib_json, dict) else {}
    stored_refs = payload.get("scripture_refs") or payload.get("scriptureRefs")
    if isinstance(stored_refs, (list, tuple, set)):
        for value in stored_refs:
            if isinstance(value, str) and value and value not in seen:
                seen.add(value)
                refs.append(value)

    # Use eager-loaded relationship if available to avoid N+1 queries
    passages = record.passages or []
    sorted_passages = sorted(
        passages,
        key=lambda p: (p.page_no or 0, p.t_start or 0.0, p.start_char or 0),
    )

    for passage in sorted_passages:
        osis_ref = passage.osis_ref
        if isinstance(osis_ref, str) and osis_ref and osis_ref not in seen:
            seen.add(osis_ref)
            refs.append(osis_ref)

    return tuple(refs)


def _document_from_record(session: Session, record: DocumentRecord) -> Document:
    """Convert a persistence model into the domain aggregate."""

    title = record.title or record.id
    source = (
        record.collection
        or record.source_type
        or record.source_url
        or "unknown"
    )
    metadata = DocumentMetadata(
        title=title,
        source=source,
        language=_extract_language(record),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )

    scripture_refs = _extract_scripture_refs(session, record)
    tags = tuple(_extract_tags(record))

    return Document(
        id=DocumentId(record.id),
        metadata=metadata,
        scripture_refs=scripture_refs,
        tags=tags,
        checksum=record.sha256,
    )


def _list_documents(
    registry: AdapterRegistry,
    *,
    limit: int = 20,
    session: Session | None = None,
) -> list[Document]:
    """Return a list of documents ordered by recency."""

    normalised_limit = max(1, int(limit)) if isinstance(limit, int) else 20

    with _maybe_session_scope(registry, session) as session:
        stmt = (
            select(DocumentRecord)
            .options(
                selectinload(DocumentRecord.passages).load_only(
                    Passage.osis_ref,
                    Passage.page_no,
                    Passage.t_start,
                    Passage.start_char,
                )
            )
            .order_by(DocumentRecord.created_at.desc())
            .limit(normalised_limit)
        )
        records = session.scalars(stmt).all()
        return [_document_from_record(session, record) for record in records]


def _get_document(
    registry: AdapterRegistry,
    document_id: DocumentId,
    session: Session | None = None,
) -> Document | None:
    """Fetch a single document by identifier."""

    with _maybe_session_scope(registry, session) as session:
        stmt = (
            select(DocumentRecord)
            .where(DocumentRecord.id == str(document_id))
            .options(
                selectinload(DocumentRecord.passages).load_only(
                    Passage.osis_ref,
                    Passage.page_no,
                    Passage.t_start,
                    Passage.start_char,
                )
            )
        )
        record = session.scalars(stmt).one_or_none()
        if record is None:
            return None
        return _document_from_record(session, record)


def _ingest_document(registry: AdapterRegistry, document: Document) -> DocumentId:
    """Persist minimal document metadata originating from GraphQL."""

    with _session_scope(registry) as session:
        record = session.get(DocumentRecord, str(document.id))
        if record is None:
            record = DocumentRecord(id=str(document.id))

        record.title = document.metadata.title
        if document.metadata.source:
            record.collection = document.metadata.source
        record.source_type = record.source_type or "graphql"
        if document.metadata.created_at is not None:
            record.created_at = document.metadata.created_at
        if document.metadata.updated_at is not None:
            record.updated_at = document.metadata.updated_at
        if document.checksum:
            record.sha256 = document.checksum

        existing_payload = record.bib_json if isinstance(record.bib_json, dict) else {}
        payload = dict(existing_payload)
        if document.metadata.language:
            payload.setdefault("language", document.metadata.language)
        if document.scripture_refs:
            payload["scripture_refs"] = list(document.scripture_refs)
        if document.tags:
            payload_tags = list(payload.get("tags") or [])
            payload_tags.extend(document.tags)
            deduped_tags: list[str] = []
            seen_tags: set[str] = set()
            for tag in payload_tags:
                if isinstance(tag, str) and tag and tag not in seen_tags:
                    seen_tags.add(tag)
                    deduped_tags.append(tag)
            payload["tags"] = deduped_tags
            record.topics = deduped_tags or None
        record.bib_json = payload or None

        session.add(record)
        session.commit()

    return document.id


def _retire_document(registry: AdapterRegistry, document_id: DocumentId) -> None:
    """Remove a document and its dependent records."""

    with _session_scope(registry) as session:
        record = session.get(DocumentRecord, str(document_id))
        if record is None:
            return
        session.delete(record)
        session.commit()


@lru_cache(maxsize=1)
def resolve_application() -> Tuple[ApplicationContainer, AdapterRegistry]:
    """Initialise the application container and adapter registry."""

    registry = AdapterRegistry()
    registry.register("settings", get_settings)
    registry.register("engine", get_engine)
    registry.register(
        "research_notes_repository_factory",
        lambda: SqlAlchemyResearchNoteRepositoryFactory(),
    )
    registry.register(
        "hypotheses_repository_factory",
        lambda: SqlAlchemyHypothesisRepositoryFactory(),
    )

    # Collection repository factory - returns a factory callable
    def _collection_repository_factory(session: Session) -> SQLAlchemyCollectionRepository:
        return SQLAlchemyCollectionRepository(session)

    registry.register(
        "collection_repository_factory",
        lambda: _collection_repository_factory,
    )

    def _build_research_service_factory() -> Callable[[Session], ResearchService]:
        from exegesis.domain.research import fetch_dss_links

        notes_factory = registry.resolve("research_notes_repository_factory")
        hypotheses_factory = registry.resolve("hypotheses_repository_factory")

        def _factory(session: Session) -> ResearchService:
            notes_repository = notes_factory(session)
            hypotheses_repository = hypotheses_factory(session)
            return ResearchService(
                notes_repository,
                hypothesis_repository=hypotheses_repository,
                fetch_dss_links_func=fetch_dss_links,
            )

        return _factory

    registry.register("research_service_factory", _build_research_service_factory)

    def _build_collection_service_factory():
        """Build a factory for CollectionService instances."""
        from exegesis.application.services.collections import CollectionService

        collection_repo_factory = registry.resolve("collection_repository_factory")

        def _factory(session: Session) -> CollectionService:
            collection_repository = collection_repo_factory(session)
            return CollectionService(collection_repository)

        return _factory

    registry.register("collection_service_factory", _build_collection_service_factory)

    _run_adapter_hooks(registry)

    def _build_embedding_rebuild_service(registry: AdapterRegistry) -> EmbeddingRebuildService:
        def _create_embedding_service() -> object:
            backend_factory = registry.resolve(EMBEDDING_BACKEND_FACTORY_PORT)
            return backend_factory()

        sanitize_passage_text = registry.resolve(EMBEDDING_SANITIZE_PORT)
        try:
            cache_clearer = registry.resolve(EMBEDDING_CACHE_CLEARER_PORT)
        except LookupError:
            cache_clearer = None

        embedding_service = LazyEmbeddingBackend(_create_embedding_service)

        def _session_factory() -> Session:
            engine = registry.resolve("engine")
            return Session(engine)

        def _repository_factory(session: Session):
            return SQLAlchemyPassageEmbeddingRepository(session)

        return EmbeddingRebuildService(
            session_factory=_session_factory,
            repository_factory=_repository_factory,
            embedding_service=embedding_service,
            sanitize_text=sanitize_passage_text,
            cache_clearer=cache_clearer,
        )

    embedding_rebuild_service = _build_embedding_rebuild_service(registry)
    registry.register(
        "embedding_rebuild_service", lambda: embedding_rebuild_service
    )

    def _build_ingest_callable() -> Callable[[Document], DocumentId]:
        return lambda document: _ingest_document(registry, document)

    def _build_retire_callable() -> Callable[[DocumentId], None]:
        return lambda document_id: _retire_document(registry, document_id)

    def _build_get_callable() -> Callable[..., Document | None]:
        return lambda document_id, session=None: _get_document(
            registry, document_id, session=session
        )

    def _build_list_callable() -> Callable[..., list[Document]]:
        def _runner(
            *, limit: int = 20, session: Session | None = None
        ) -> list[Document]:
            return _list_documents(registry, limit=limit, session=session)

        return _runner

    container = ApplicationContainer(
        ingest_document=_build_ingest_callable(),
        retire_document=_build_retire_callable(),
        get_document=_build_get_callable(),
        list_documents=_build_list_callable(),
        research_service_factory=_build_research_service_factory(),
    )
    return container, registry


__all__ = [
    "EMBEDDING_BACKEND_FACTORY_PORT",
    "EMBEDDING_CACHE_CLEARER_PORT",
    "EMBEDDING_SANITIZE_PORT",
    "register_adapter_hook",
    "resolve_application",
]
