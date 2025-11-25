from __future__ import annotations

from collections.abc import Generator, Iterator

import os
from unittest.mock import patch
import pytest

from tests.integration._db import ensure_duplicate_detection_baseline
from tests.integration._stubs import (
    install_audio_stubs,
    install_celery_stub,
    install_duplicate_detection_stub,
    install_openai_stub,
    install_sklearn_stub,
)

try:  # pragma: no cover - optional SQLAlchemy dependency
    from sqlalchemy import create_engine
    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import Session, sessionmaker
    from sqlalchemy.pool import StaticPool
except (ModuleNotFoundError, ImportError):  # pragma: no cover - allow lightweight environments
    create_engine = None  # type: ignore[assignment]
    Engine = Session = object  # type: ignore[assignment]
    sessionmaker = StaticPool = None  # type: ignore[assignment]
    Base = None  # type: ignore[assignment]
    run_sql_migrations = None  # type: ignore[assignment]
else:
    from exegesis.adapters.persistence import Base

    try:  # pragma: no cover - migrations optional in light environments
        from exegesis.infrastructure.api.app.db.run_sql_migrations import run_sql_migrations
    except (ModuleNotFoundError, ImportError):  # pragma: no cover - lightweight test runs
        run_sql_migrations = None  # type: ignore[assignment]


install_sklearn_stub()
install_celery_stub()
install_audio_stubs()
install_openai_stub()
install_duplicate_detection_stub()


@pytest.fixture(scope="session")
def sqlite_memory_engine() -> Iterator[Engine]:
    """Create the in-memory SQLite engine once per session."""

    if create_engine is None or Base is None or StaticPool is None:
        pytest.skip("sqlalchemy not installed")

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    if run_sql_migrations is not None:
        run_sql_migrations(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(scope="function")
def sqlite_session(sqlite_memory_engine: Engine) -> Generator[Session, None, None]:
    """Wrap each test in a transaction that is rolled back afterwards."""

    if sessionmaker is None:
        pytest.skip("sqlalchemy not installed")

    connection = sqlite_memory_engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection, future=True)
    session = SessionLocal()
    ensure_duplicate_detection_baseline(session)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture(scope="session", autouse=True)
def integration_session_environment() -> Iterator[None]:
    """Provide consistent configuration for integration scenarios (session-scoped)."""

    from exegesis.infrastructure.api.app.db import query_optimizations
    from exegesis.application.facades.settings import get_settings
    from exegesis.application.facades.runtime import clear_generated_dev_key

    # Manually update os.environ to ensure global visibility
    old_environ = dict(os.environ)
    updates = {
        "SETTINGS_SECRET_KEY": "integration-secret",
        "EXEGESIS_API_KEYS": '["pytest-default-key"]',
        "EXEGESIS_ALLOW_INSECURE_STARTUP": "1",
        "EXEGESIS_ENVIRONMENT": "test",
        "EXEGESIS_FORCE_EMBEDDING_FALLBACK": "1",
        "CREATOR_VERSE_ROLLUPS_ASYNC_REFRESH": "0",
    }
    os.environ.update(updates)

    # Clear any previously generated dev key to ensure we use the configured API keys
    clear_generated_dev_key()

    # Clear cache once to ensure these settings take effect
    get_settings.cache_clear()

    try:
        # Mock out query optimizations to avoid side effects
        with patch.object(query_optimizations, "record_histogram"), patch.object(
            query_optimizations, "record_counter"
        ):
            yield
    finally:
        # Restore environment
        os.environ.clear()
        os.environ.update(old_environ)
        get_settings.cache_clear()
        clear_generated_dev_key()
