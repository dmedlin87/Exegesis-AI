"""Register adapters needed by the embedding rebuild workflows."""

from __future__ import annotations

from exegesis.adapters import AdapterRegistry
from exegesis.application.services.bootstrap import (
    EMBEDDING_BACKEND_FACTORY_PORT,
    EMBEDDING_CACHE_CLEARER_PORT,
    EMBEDDING_SANITIZE_PORT,
    register_adapter_hook,
)


def _register_embedding_rebuild_adapters(registry: AdapterRegistry) -> None:
    """Register the embedding backend, sanitizer, and cache clearer."""

    from exegesis.infrastructure.api.app.library.ingest import embeddings
    from exegesis.infrastructure.api.app.library.ingest import sanitizer

    registry.register(
        EMBEDDING_BACKEND_FACTORY_PORT,
        lambda: lambda: embeddings.get_embedding_service(),
        allow_override=True,
    )
    registry.register(
        EMBEDDING_SANITIZE_PORT,
        lambda: sanitizer.sanitize_passage_text,
        allow_override=True,
    )
    registry.register(
        EMBEDDING_CACHE_CLEARER_PORT,
        lambda: embeddings.clear_embedding_cache,
        allow_override=True,
    )


_registrations_installed = False


def ensure_embedding_rebuild_adapters_registered() -> None:
    """Ensure the embedding rebuild adapters have been registered."""

    global _registrations_installed
    if _registrations_installed:
        return
    register_adapter_hook(_register_embedding_rebuild_adapters)
    _registrations_installed = True


ensure_embedding_rebuild_adapters_registered()

