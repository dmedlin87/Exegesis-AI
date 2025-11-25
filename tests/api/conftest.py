"""Shared test configuration for API-level tests.

Architecture Overview
---------------------
All API tests share a single FastAPI ``app`` instance and a session-scoped
``_global_test_client`` (``TestClient(app)``). This design minimizes overhead
by avoiding repeated app startup/shutdown cycles.

Fixture Layering
^^^^^^^^^^^^^^^^
::

    Test
      └─ api_test_client (function-scoped, yields _global_test_client)
           ├─ api_engine: per-test connection + transaction with SAVEPOINT isolation
           ├─ _bypass_authentication: overrides require_principal (unless @no_auth_override)
           └─ _stub_external_integrations: session-scoped stubs for Zotero, telemetry, etc.

DB Isolation
^^^^^^^^^^^^
- ``api_engine`` creates a per-test connection on a shared SQLite engine
- A ``Session`` with ``join_transaction_mode="create_savepoint"`` ensures that
  ``session.commit()`` in routes/services operates within nested transactions
- The outer transaction is rolled back at teardown, guaranteeing no persistent changes

Thread Safety
^^^^^^^^^^^^^
The shared app design relies on:
1. **xdist grouping**: Tests in the same module run in the same worker (``xdist_group``
   is set per-module in ``pytest_collection_modifyitems``)
2. **Per-test cleanup**: ``api_engine`` and ``_bypass_authentication`` set/clear
   ``app.dependency_overrides`` per test

This is safe for current pytest-xdist parallelisation but would need revisiting if
tests within a module ever run concurrently against the same app object.

External Services
^^^^^^^^^^^^^^^^^
- Embeddings, PDFs, sklearn, opentelemetry are stubbed at import time (top of file)
- Zotero, realtime, telemetry, AI trails are stubbed via ``_stub_external_integrations``
- Auth is bypassed by default; use ``@pytest.mark.no_auth_override`` to enforce auth
"""
from __future__ import annotations

import contextlib
import os
import shutil
import sys
import types
from collections.abc import Iterator

os.environ.setdefault("EXEGESIS_ALLOW_REAL_FASTAPI", "1")

os.environ.setdefault("SETTINGS_SECRET_KEY", "test-secret-key")
os.environ.setdefault("EXEGESIS_API_KEYS", '["pytest-default-key"]')
os.environ.setdefault("EXEGESIS_ALLOW_INSECURE_STARTUP", "1")
os.environ.setdefault("EXEGESIS_ENVIRONMENT", "development")
os.environ.setdefault("EXEGESIS_FORCE_EMBEDDING_FALLBACK", "1")


class _StubFlagModel:
    """Lightweight embedding stub used during API tests."""

    def __init__(self, *_, **__):
        self._dimension = 1024

    def encode(self, texts):
        vectors = []
        for index, _ in enumerate(texts):
            base = float((index % 100) + 1)
            vectors.append(
                [((base + offset) % 100) / 100.0 for offset in range(self._dimension)]
            )
        return vectors


flag_module = types.ModuleType("FlagEmbedding")
flag_module.FlagModel = _StubFlagModel  # type: ignore[attr-defined]
sys.modules.setdefault("FlagEmbedding", flag_module)


def _register_pypdf_stub() -> None:
    """Provide a lightweight :mod:`pypdf` substitute for test environments."""

    if "pypdf" in sys.modules:
        return

    pypdf_module = types.ModuleType("pypdf")

    class _StubPage:
        def extract_text(self):  # pragma: no cover - trivial stand-in
            return ""

    class _StubPdfReader:
        def __init__(self, *_args, **_kwargs):
            self.pages = []
            self.is_encrypted = False

        def decrypt(self, *_args, **_kwargs):  # pragma: no cover - simple stub
            self.is_encrypted = False

    pypdf_module.PdfReader = _StubPdfReader  # type: ignore[attr-defined]

    errors_module = types.ModuleType("pypdf.errors")

    class _StubPdfReadError(Exception):
        pass

    class _StubFileNotDecryptedError(Exception):
        pass

    errors_module.PdfReadError = _StubPdfReadError  # type: ignore[attr-defined]
    errors_module.FileNotDecryptedError = _StubFileNotDecryptedError  # type: ignore[attr-defined]

    sys.modules.setdefault("pypdf", pypdf_module)
    sys.modules.setdefault("pypdf.errors", errors_module)


_register_pypdf_stub()


def _register_opentelemetry_stub() -> None:
    """Install a minimal :mod:`opentelemetry` facade used in workflow tests."""

    if "opentelemetry" in sys.modules:
        return

    otel_module = types.ModuleType("opentelemetry")
    trace_module = types.ModuleType("opentelemetry.trace")
    otel_module.__path__ = []  # type: ignore[attr-defined]

    class _StubSpan:
        def __init__(self):
            self.attributes: dict[str, object] = {}

        def set_attribute(self, key: str, value: object) -> None:  # pragma: no cover - simple stub
            self.attributes[key] = value

    class _StubTracer:
        def start_as_current_span(self, name: str, **attributes: object):
            @contextlib.contextmanager
            def _manager():
                span = _StubSpan()
                for key, value in attributes.items():
                    span.set_attribute(key, value)
                yield span

            return _manager()

    def _get_tracer(_name: str = "Exegesis AI") -> _StubTracer:  # pragma: no cover - helper
        return _StubTracer()

    trace_module.get_tracer = _get_tracer  # type: ignore[attr-defined]
    otel_module.trace = trace_module  # type: ignore[attr-defined]

    sys.modules.setdefault("opentelemetry", otel_module)
    sys.modules.setdefault("opentelemetry.trace", trace_module)


_register_opentelemetry_stub()


def _register_sklearn_stubs() -> None:
    """Provide lightweight sklearn replacements for test environments."""

    if "sklearn" in sys.modules:
        return

    sklearn_module = types.ModuleType("sklearn")

    sklearn_ensemble = types.ModuleType("sklearn.ensemble")

    class _StubIsolationForest:
        def __init__(self, *_, **__):
            self._scores: list[float] | None = None

        def fit(self, embeddings):
            count = len(embeddings) if embeddings is not None else 0
            self._scores = [-0.1 for _ in range(count)]
            return self

        def decision_function(self, embeddings):
            scores = self._scores or [-0.1 for _ in range(len(embeddings) or 0)]
            return scores

        def predict(self, embeddings):
            return [-1 for _ in range(len(embeddings) or 0)]

    sklearn_ensemble.IsolationForest = _StubIsolationForest  # type: ignore[attr-defined]
    sklearn_module.ensemble = sklearn_ensemble  # type: ignore[attr-defined]

    sklearn_cluster = types.ModuleType("sklearn.cluster")

    class _StubDBSCAN:
        def __init__(self, *_, **__):
            pass

        def fit_predict(self, points):
            return [0 for _ in range(len(points) or 0)]

    sklearn_cluster.DBSCAN = _StubDBSCAN  # type: ignore[attr-defined]
    sklearn_module.cluster = sklearn_cluster  # type: ignore[attr-defined]

    sklearn_pipeline = types.ModuleType("sklearn.pipeline")

    class _StubPipeline:
        def __init__(self, steps, **_):
            self.steps = steps

        def fit(self, *_args, **_kwargs):
            return self

        def predict(self, data):
            return [0 for _ in range(len(data) or 0)]

        def transform(self, data):
            return data

    sklearn_pipeline.Pipeline = _StubPipeline  # type: ignore[attr-defined]
    sklearn_module.pipeline = sklearn_pipeline  # type: ignore[attr-defined]

    sklearn_feature = types.ModuleType("sklearn.feature_extraction")
    sklearn_feature_text = types.ModuleType("sklearn.feature_extraction.text")

    class _StubTfidfVectorizer:
        def __init__(self, *_, **__):
            pass

        def fit(self, *_args, **_kwargs):
            return self

        def transform(self, data):
            return data

        def fit_transform(self, data, *_, **__):
            return data

    sklearn_feature_text.TfidfVectorizer = _StubTfidfVectorizer  # type: ignore[attr-defined]
    sklearn_feature.text = sklearn_feature_text  # type: ignore[attr-defined]
    sklearn_module.feature_extraction = sklearn_feature  # type: ignore[attr-defined]

    sklearn_linear = types.ModuleType("sklearn.linear_model")

    class _StubLogisticRegression:
        def __init__(self, *_, **__):
            pass

        def fit(self, *_args, **_kwargs):
            return self

        def predict(self, data):
            return [0 for _ in range(len(data) or 0)]

    sklearn_linear.LogisticRegression = _StubLogisticRegression  # type: ignore[attr-defined]
    sklearn_module.linear_model = sklearn_linear  # type: ignore[attr-defined]

    sklearn_preprocessing = types.ModuleType("sklearn.preprocessing")

    class _StubStandardScaler:
        def fit(self, data, *_args, **_kwargs):
            return self

        def transform(self, data):
            return data

        def fit_transform(self, data, *_args, **_kwargs):
            return data

    sklearn_preprocessing.StandardScaler = _StubStandardScaler  # type: ignore[attr-defined]
    sklearn_module.preprocessing = sklearn_preprocessing  # type: ignore[attr-defined]

    sklearn_impute = types.ModuleType("sklearn.impute")

    class _StubSimpleImputer:
        def __init__(self, *_, **__):
            pass

        def fit(self, data, *_args, **_kwargs):
            return self

        def transform(self, data):
            return data

        def fit_transform(self, data, *_args, **_kwargs):
            return data

    sklearn_impute.SimpleImputer = _StubSimpleImputer  # type: ignore[attr-defined]
    sklearn_module.impute = sklearn_impute  # type: ignore[attr-defined]

    sklearn_ensemble.HistGradientBoostingRegressor = _StubIsolationForest  # type: ignore[attr-defined]

    sys.modules.setdefault("sklearn", sklearn_module)
    sys.modules.setdefault("sklearn.ensemble", sklearn_ensemble)
    sys.modules.setdefault("sklearn.cluster", sklearn_cluster)
    sys.modules.setdefault("sklearn.pipeline", sklearn_pipeline)
    sys.modules.setdefault("sklearn.feature_extraction", sklearn_feature)
    sys.modules.setdefault("sklearn.feature_extraction.text", sklearn_feature_text)
    sys.modules.setdefault("sklearn.linear_model", sklearn_linear)
    sys.modules.setdefault("sklearn.preprocessing", sklearn_preprocessing)
    sys.modules.setdefault("sklearn.impute", sklearn_impute)


_register_sklearn_stubs()



from pathlib import Path

import pytest

pytestmark = pytest.mark.schema
from fastapi import Request as FastAPIRequest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from exegesis.infrastructure.api.app.main import app
from exegesis.infrastructure.api.app.db import run_sql_migrations as migrations_module
from exegesis.application.facades import database as database_module
from exegesis.application.facades.database import Base, configure_engine, get_engine
from exegesis.infrastructure.api.app.adapters.security import require_principal


@pytest.fixture(scope="session", autouse=True)
def _stub_external_integrations() -> Iterator[None]:
    """Replace external integrations with deterministic test doubles."""

    monkeypatch = pytest.MonkeyPatch()
    from exegesis.infrastructure.api.app.export import zotero as _zotero_module

    def _fake_zotero_export(sources, csl_entries, api_key, **kwargs):  # pragma: no cover - simple stub
        total = len(sources or [])
        return {
            "success": True,
            "exported_count": total,
            "failed_count": 0,
            "errors": [],
            "items": [],
        }

    monkeypatch.setattr(
        _zotero_module,
        "export_to_zotero",
        _fake_zotero_export,
        raising=False,
    )
    monkeypatch.setattr(
        _zotero_module,
        "verify_zotero_credentials",
        lambda *a, **kw: True,
        raising=False,
    )

    monkeypatch.setattr(
        "exegesis.infrastructure.api.app.routes.realtime.publish_notebook_update",
        lambda *a, **kw: None,
        raising=False,
    )

    def _instrument_stub(*_args, **_kwargs):
        @contextlib.contextmanager
        def _manager():
            yield types.SimpleNamespace(set_attribute=lambda *a, **kw: None)

        return _manager()

    monkeypatch.setattr(
        "exegesis.application.facades.telemetry.instrument_workflow",
        _instrument_stub,
        raising=False,
    )
    monkeypatch.setattr(
        "exegesis.infrastructure.api.app.research.ai.trails._compute_input_hash",
        lambda input_payload, tool, action: str(
            (tool or "", action or "", repr(input_payload))
        ),
        raising=False,
    )

    try:
        yield
    finally:
        monkeypatch.undo()


@pytest.fixture(autouse=True)
def _bypass_authentication(request: pytest.FixtureRequest):
    """Permit unauthenticated access for API tests unless explicitly disabled."""

    if request.node.get_closest_marker("no_auth_override"):
        yield
        return

    def _principal_override(fastapi_request: FastAPIRequest):
        principal = {"method": "override", "subject": "test"}
        fastapi_request.state.principal = principal
        return principal

    app.dependency_overrides[require_principal] = _principal_override
    try:
        yield
    finally:
        app.dependency_overrides.pop(require_principal, None)


@pytest.fixture(autouse=True)
def _disable_migrations(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prevent migrations from running during API startup.

    Migrations are already applied by the integration_database_url fixture,
    so we don't need to run them again during FastAPI app lifespan startup.
    """

    if request.node.get_closest_marker("schema"):
        yield
        return

    # Replace run_sql_migrations with a no-op since migrations were already
    # applied by the fixture that created the test database
    def _noop_run_sql_migrations(
        engine=None,
        migrations_path=None,
        *,
        force: bool = False,
    ) -> list[str]:
        return []

    monkeypatch.setattr(
        migrations_module,
        "run_sql_migrations",
        _noop_run_sql_migrations,
    )
    monkeypatch.setattr(
        "exegesis.infrastructure.api.app.bootstrap.lifecycle.run_sql_migrations",
        _noop_run_sql_migrations,
    )

    yield


@pytest.fixture(scope="session", autouse=True)
def _skip_heavy_startup() -> None:
    monkeypatch = pytest.MonkeyPatch()
    """Disable expensive FastAPI lifespan setup steps for API tests."""

    from sqlalchemy import text as _sql_text
    from exegesis.infrastructure.api.app.db import seeds as _seeds_module

    original_seed_reference_data = _seeds_module.seed_reference_data

    def _maybe_seed_reference_data(session) -> None:
        """Invoke the real seeders when the database still needs backfilling."""

        needs_seeding = True
        try:
            bind = session.get_bind()
            if bind is not None:
                try:
                    perspective_present = bool(
                        session.execute(
                            _sql_text(
                                "SELECT 1 FROM pragma_table_info('contradiction_seeds') "
                                "WHERE name = 'perspective'"
                            )
                        ).first()
                    )
                except Exception:
                    perspective_present = False
                if perspective_present:
                    try:
                        has_rows = bool(
                            session.execute(
                                _sql_text(
                                    "SELECT 1 FROM contradiction_seeds LIMIT 1"
                                )
                            ).first()
                        )
                    except Exception:
                        has_rows = False
                    needs_seeding = not has_rows
                else:
                    needs_seeding = True
        except Exception:
            needs_seeding = True

        if needs_seeding:
            original_seed_reference_data(session)

    monkeypatch.setattr(
        "exegesis.infrastructure.api.app.bootstrap.lifecycle.seed_reference_data",
        _maybe_seed_reference_data,
        raising=False,
    )
    monkeypatch.setattr(
        "exegesis.infrastructure.api.app.bootstrap.lifecycle.start_discovery_scheduler",
        lambda: None,
        raising=False,
    )
    monkeypatch.setattr(
        "exegesis.infrastructure.api.app.bootstrap.lifecycle.stop_discovery_scheduler",
        lambda: None,
        raising=False,
    )

    try:
        yield
    finally:
        monkeypatch.undo()


@pytest.fixture(scope="session")
def _api_engine_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Materialise a migrated SQLite database once per test session."""
    from exegesis.infrastructure.api.app.db.run_sql_migrations import run_sql_migrations

    template_dir = tmp_path_factory.mktemp("api-engine-template")
    template_path = template_dir / "api.sqlite"
    engine = create_engine(f"sqlite:///{template_path}", future=True)
    try:
        Base.metadata.create_all(bind=engine)
        run_sql_migrations(engine)
    finally:
        engine.dispose()
    return template_path


@pytest.fixture(scope="session")
def _shared_api_engine(_api_engine_template: Path):
    """Shared engine instance connected to the template database."""
    engine = create_engine(f"sqlite:///{_api_engine_template}", future=True)
    yield engine
    engine.dispose()


@pytest.fixture()
def api_engine(_shared_api_engine):
    """Provide a transaction-isolated database environment.

    Instead of creating a new database file per test, this fixture:
    1. Connects to the shared session-scoped engine
    2. Starts a transaction
    3. Uses nested transactions (SAVEPOINT) to isolate app commits
    4. Overrides get_session to use a session bound to this transaction
    5. Rolls back the transaction at teardown

    This mimics a fresh database for every test but is much faster (~instant).
    """
    from sqlalchemy import event
    from sqlalchemy.orm import Session
    from exegesis.application.facades import database as database_module

    connection = _shared_api_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    # Override global get_session for direct usage in fixtures/tests
    def _stub_get_session():
        yield session

    original_get_session = database_module.get_session
    database_module.get_session = _stub_get_session

    # Override FastAPI dependency for route handlers
    # Note: We key off the *original* function object because that's what Depends uses
    app.dependency_overrides[original_get_session] = _stub_get_session

    try:
        yield connection
    finally:
        app.dependency_overrides.pop(original_get_session, None)
        database_module.get_session = original_get_session
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture(scope="session")
def _global_test_client() -> Iterator[TestClient]:
    """Create a single TestClient instance for the entire session.

    This avoids the overhead of running FastAPI startup/shutdown events for every test.
    """
    with TestClient(app) as client:
        yield client


@pytest.fixture()
def api_test_client(api_engine, _global_test_client) -> TestClient:
    """Yield a ``TestClient`` bound to the isolated transaction.

    This fixture ensures:
    1. The DB transaction is active (via api_engine)
    2. The global TestClient is reused (via _global_test_client)
    """
    # api_engine fixture handles the dependency overrides on the app
    # The shared client will see these overrides because they are set on the app instance
    return _global_test_client
