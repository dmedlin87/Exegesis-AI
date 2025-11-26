"""Heavy fixtures for schema, pgvector, and integration tests.

This module is loaded conditionally when EXEGESIS_SKIP_HEAVY_FIXTURES is not set.
It contains fixtures that require SQLAlchemy, testcontainers, and other heavy
dependencies. Splitting them here reduces parse time for lightweight test runs.

Fixtures
--------
pgvector_db : session
    Provisions a Postgres+pgvector container for integration tests.
    Requires ``--pgvector`` flag.

pgvector_engine : session
    SQLAlchemy engine connected to the pgvector database.

integration_database_url : session
    Returns database URL for schema tests (pgvector or SQLite).

integration_engine : session
    Engine bound to the integration database.

schema_isolation : function
    Transaction-based isolation for @pytest.mark.schema tests.

application_container : function
    Isolated application container for testing.
"""

from __future__ import annotations

import contextlib
import importlib
import os
from collections.abc import Callable, Generator, Iterator
from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest

if TYPE_CHECKING:
    from exegesis.adapters import AdapterRegistry
    from exegesis.application import ApplicationContainer
    from testcontainers.postgres import PostgresContainer

# Lazy imports for SQLAlchemy to avoid import-time cost when not needed
_sqlalchemy_loaded = False
create_engine = None
text = None
Connection = object
Engine = object
Session = object
sessionmaker = None
event = None


def _ensure_sqlalchemy():
    """Load SQLAlchemy on first use."""
    global _sqlalchemy_loaded, create_engine, text, Connection, Engine, Session, sessionmaker, event
    if _sqlalchemy_loaded:
        return True
    try:
        import sqlalchemy
        from sqlalchemy import create_engine as _create_engine, text as _text
        from sqlalchemy.engine import Connection as _Connection, Engine as _Engine
        from sqlalchemy.orm import Session as _Session, sessionmaker as _sessionmaker
        create_engine = _create_engine
        text = _text
        Connection = _Connection
        Engine = _Engine
        Session = _Session
        sessionmaker = _sessionmaker
        try:
            event = sqlalchemy.event
        except AttributeError:
            event = importlib.import_module("sqlalchemy.event")
        _sqlalchemy_loaded = True
        return True
    except (ModuleNotFoundError, ImportError):
        return False


# Lazy imports for pgvector fixtures
_pgvector_fixtures_loaded = False
PGVectorDatabase = None
PGVectorClone = None
provision_pgvector_database = None
isolated_application_container = None
_APPLICATION_FACTORY_IMPORT_ERROR = None


def _ensure_pgvector_fixtures():
    """Load pgvector fixture utilities on first use."""
    global _pgvector_fixtures_loaded, PGVectorDatabase, PGVectorClone
    global provision_pgvector_database, isolated_application_container
    global _APPLICATION_FACTORY_IMPORT_ERROR

    if _pgvector_fixtures_loaded:
        return True
    try:
        from tests.fixtures.pgvector import (
            PGVectorDatabase as _PGVectorDatabase,
            PGVectorClone as _PGVectorClone,
            provision_pgvector_database as _provision_pgvector_database,
        )
        PGVectorDatabase = _PGVectorDatabase
        PGVectorClone = _PGVectorClone
        provision_pgvector_database = _provision_pgvector_database
        _pgvector_fixtures_loaded = True
    except ModuleNotFoundError:
        return False

    try:
        from tests.factories.application import (
            isolated_application_container as _isolated_application_container,
        )
        isolated_application_container = _isolated_application_container
    except ModuleNotFoundError as exc:
        _APPLICATION_FACTORY_IMPORT_ERROR = exc
        isolated_application_container = None

    return True


# Context var for schema isolation
_SCHEMA_CONNECTION: ContextVar[Any | None] = ContextVar("_SCHEMA_CONNECTION")

POSTGRES_IMAGE = os.environ.get("PYTEST_PGVECTOR_IMAGE", "pgvector/pgvector:pg15")


def _require_application_factory() -> None:
    """Skip test if application factory is unavailable."""
    if not _ensure_pgvector_fixtures() or isolated_application_container is None:
        reason = _APPLICATION_FACTORY_IMPORT_ERROR or ModuleNotFoundError("pythonbible")
        pytest.skip(f"application factory unavailable: {reason}")


@pytest.fixture(scope="session")
def pgvector_db(request: pytest.FixtureRequest) -> Iterator[Any]:
    """Provision a seeded Postgres+pgvector database for heavy integration suites.

    The fixture starts a single Testcontainer for the duration of the test
    session, applies the project's SQL migrations, and seeds the bundled
    reference datasets.
    """
    if not request.config.getoption("pgvector"):
        pytest.skip("requires --pgvector flag")

    if not _ensure_pgvector_fixtures() or provision_pgvector_database is None:
        pytest.skip("pgvector fixtures not available")

    try:
        context = provision_pgvector_database(image=POSTGRES_IMAGE)
    except ModuleNotFoundError as exc:
        pytest.skip(f"testcontainers not installed: {exc}")

    try:
        with context as database:
            yield database
    except ModuleNotFoundError as exc:
        pytest.skip(f"testcontainers not installed: {exc}")
    except Exception as exc:
        pytest.skip(f"Unable to start Postgres Testcontainer: {exc}")


@pytest.fixture(scope="session")
def pgvector_container(pgvector_db) -> "PostgresContainer":
    """Return the underlying Testcontainer for backwards-compatible fixtures."""
    return pgvector_db.container


@pytest.fixture(scope="session")
def pgvector_database_url(pgvector_db) -> str:
    """Expose the SQLAlchemy URL for the seeded pgvector template database."""
    return pgvector_db.url


@pytest.fixture(scope="session")
def pgvector_engine(pgvector_db) -> Iterator[Any]:
    """Yield an engine connected to the seeded pgvector template database."""
    engine = pgvector_db.create_engine()
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def pgvector_migrated_database_url(pgvector_db) -> str:
    """Return the URL of the migrated pgvector database (for legacy callers)."""
    return pgvector_db.url


def _initialise_shared_database(db_path: Path) -> str:
    """Create and migrate a SQLite database."""
    if not _ensure_sqlalchemy():
        pytest.skip("sqlalchemy not installed")

    from exegesis.application.facades.database import Base
    from exegesis.infrastructure.api.app.db.run_sql_migrations import run_sql_migrations

    url = f"sqlite:///{db_path}"
    engine = create_engine(url, future=True)
    try:
        Base.metadata.create_all(bind=engine)
        run_sql_migrations(engine)
    finally:
        engine.dispose()

    return url


def _sqlite_database_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """Create a SQLite database URL with migrations applied."""
    if not _ensure_sqlalchemy():
        pytest.skip("sqlalchemy not installed")

    from exegesis.infrastructure.api.app.db.run_sql_migrations import run_sql_migrations
    from exegesis.application.facades.database import Base

    database_dir = tmp_path_factory.mktemp("sqlite", numbered=True)
    path = database_dir / "test.db"
    url = f"sqlite:///{path}"

    engine = create_engine(url, future=True)
    try:
        Base.metadata.create_all(bind=engine)
        migrations_module = importlib.import_module(
            "exegesis.infrastructure.api.app.db.run_sql_migrations"
        )
        original_index_helper = getattr(
            migrations_module, "_ensure_performance_indexes", None
        )
        try:
            if original_index_helper is not None:
                migrations_module._ensure_performance_indexes = lambda _engine: []
            run_sql_migrations(engine)
        finally:
            if original_index_helper is not None:
                migrations_module._ensure_performance_indexes = original_index_helper
        yield url
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def shared_test_database(tmp_path_factory: pytest.TempPathFactory) -> str:
    """Create a session-scoped SQLite database that can be reused across tests."""
    database_dir = tmp_path_factory.mktemp("shared_db", numbered=False)
    db_path = database_dir / "test.db"
    return _initialise_shared_database(db_path)


@pytest.fixture(scope="session")
def integration_database_url(
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[str]:
    """Return a database URL for integration tests using schema migrations.

    Requires the ``--schema`` flag (which is automatically implied if
    ``--pgvector`` is used).

    * When ``--pgvector`` is enabled, the URL of the migrated pgvector
      database is returned via ``pgvector_migrated_database_url``.
    * Otherwise, a throwaway SQLite database is created under the session's
      temporary directory.
    """
    if request.config.getoption("pgvector"):
        pgvector_url = request.getfixturevalue("pgvector_migrated_database_url")
        yield pgvector_url
        return

    yield from _sqlite_database_url(tmp_path_factory)


@pytest.fixture(scope="session")
def integration_engine(integration_database_url: str) -> Iterator[Any]:
    """Provide a SQLAlchemy engine bound to the integration database."""
    if not _ensure_sqlalchemy():
        pytest.skip("sqlalchemy not installed")

    engine = create_engine(integration_database_url, future=True)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(scope="function")
def db_transaction(integration_engine) -> Generator[Any, None, None]:
    """Wrap tests in a transaction that is rolled back afterwards."""
    connection = integration_engine.connect()
    transaction = connection.begin()
    try:
        yield connection
    finally:
        transaction.rollback()
        connection.close()


@pytest.fixture(scope="function")
def integration_session(request: pytest.FixtureRequest) -> Generator[Any, None, None]:
    """Return a SQLAlchemy ``Session`` bound to an isolated transaction."""
    if not _ensure_sqlalchemy() or sessionmaker is None:
        pytest.skip("sqlalchemy not installed")

    connection = _SCHEMA_CONNECTION.get(None)
    if connection is None:
        db_transaction = request.getfixturevalue("db_transaction")
        connection = cast(Connection, db_transaction)
    else:
        connection = cast(Connection, connection)

    SessionFactory = sessionmaker(bind=connection, future=True)
    session = SessionFactory()
    nested = session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, transaction) -> None:
        if transaction.nested and not transaction._parent.nested:
            sess.begin_nested()

    try:
        yield session
    finally:
        try:
            if nested.is_active:
                nested.rollback()
        except Exception:
            pass
        event.remove(session, "after_transaction_end", _restart_savepoint)
        session.close()


@pytest.fixture(scope="function")
def schema_isolation(db_transaction: Any) -> Iterator[Any]:
    """Ensure ``@pytest.mark.schema`` tests automatically roll back state."""
    connection = cast(Connection, db_transaction)
    token = _SCHEMA_CONNECTION.set(connection)
    try:
        yield connection
    finally:
        _SCHEMA_CONNECTION.reset(token)


@pytest.fixture(scope="session", autouse=True)
def _set_database_url_env(
    request: pytest.FixtureRequest, pytestconfig: pytest.Config
) -> Generator[None, None, None]:
    """Expose the integration database URL via ``DATABASE_URL``.

    Only activates when ``--schema`` or ``--pgvector`` flags are provided.
    """
    is_fast = pytestconfig.getoption("--fast", default=False)
    needs_schema = pytestconfig.getoption("schema", default=False)

    if is_fast or not needs_schema:
        yield
        return

    integration_database_url = request.getfixturevalue("integration_database_url")
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = integration_database_url
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous


@pytest.fixture
def application_container() -> Iterator[tuple["ApplicationContainer", "AdapterRegistry"]]:
    """Yield an isolated application container and backing registry."""
    _require_application_factory()
    with isolated_application_container() as resources:
        yield resources


@pytest.fixture(scope="session")
def optimized_application_container() -> Generator[
    tuple["ApplicationContainer", "AdapterRegistry"], None, None
]:
    """Create the application container once per session for heavy suites."""
    _require_application_factory()
    with isolated_application_container() as resources:
        yield resources


@pytest.fixture
def application_container_factory():
    """Provide a factory returning isolated application containers."""
    _require_application_factory()

    def _factory(**overrides):
        return isolated_application_container(overrides=overrides or None)

    return _factory


class TestResourcePool:
    """Pool expensive resources for reuse across the test session."""

    def __init__(self) -> None:
        self._engines: dict[str, Any] = {}

    def get_db_engine(self, url: str) -> Any:
        if not _ensure_sqlalchemy():
            pytest.skip("sqlalchemy not installed")

        engine = self._engines.get(url)
        if engine is None:
            engine = create_engine(url, future=True)
            self._engines[url] = engine
        return engine

    def cleanup(self) -> None:
        for engine in self._engines.values():
            engine.dispose()
        self._engines.clear()


@pytest.fixture(scope="session")
def resource_pool() -> Generator[TestResourcePool, None, None]:
    """Expose a shared resource pool for integration-heavy tests."""
    pool = TestResourcePool()
    try:
        yield pool
    finally:
        pool.cleanup()


@pytest.fixture(scope="session")
def ml_models() -> Callable[[str], Any]:
    """Load expensive ML models lazily and cache them for reuse."""
    cache: dict[str, Any] = {}

    def _load_model_from_registry(model_name: str) -> Any:
        """Attempt to import an expensive ML model using common naming conventions."""
        candidate_modules = [
            f"exegesis.ml.models.{model_name}",
            f"exegesis.infrastructure.ml.{model_name}",
            f"exegesis.infrastructure.ml.models.{model_name}",
            f"exegesis.infrastructure.api.app.ml.{model_name}",
            f"exegesis.infrastructure.api.app.ml.models.{model_name}",
        ]

        for module_path in candidate_modules:
            with contextlib.suppress(ModuleNotFoundError, AttributeError):
                module = importlib.import_module(module_path)
                loader = getattr(module, "load_model")
                if callable(loader):
                    return loader()

        raise LookupError(f"Unable to locate loader for ML model '{model_name}'")

    def _load(model_name: str, *, loader: Callable[[], Any] | None = None) -> Any:
        if model_name not in cache:
            if loader is not None:
                cache[model_name] = loader()
            else:
                cache[model_name] = _load_model_from_registry(model_name)
        return cache[model_name]

    return _load
