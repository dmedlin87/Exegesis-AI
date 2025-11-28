"""Global pytest configuration and fixtures for Exegesis AI test suite.

Auto-Use Fixtures
-----------------
The following fixtures are applied automatically to all tests. Use the escape
hatch markers to opt-out when necessary.

**Function-scoped (per test):**

- ``stub_example_com_requests``
    Intercepts urllib requests to example.com/* and returns deterministic HTML.
    No opt-out marker (network isolation is always enforced).

- ``_bootstrap_embedding_service_stub``
    Replaces ``get_embedding_service()`` with a deterministic stub that returns
    predictable embedding vectors. Access the stub via ``bootstrap_embedding_service_stub``.

- ``mock_sleep``
    Patches ``time.sleep`` and ``asyncio.sleep`` to return immediately.
    **Opt-out:** ``@pytest.mark.allow_sleep``

**Session-scoped (once per session):**

- ``downgrade_ingestion_error_logs``
    Demotes expected ingestion error logs to WARNING level.

- ``_configure_celery_for_tests``
    Forces Celery into eager mode (``task_always_eager=True``).

- ``_set_database_url_env``
    Sets ``DATABASE_URL`` environment variable from ``integration_database_url``.
    Skipped in ``--fast`` mode.

- ``mock_sleep_session``
    Session-scoped companion to ``mock_sleep``; holds the patchers.

- ``optimize_mocks`` (from ``tests.fixtures.mocks``)
    Patches ``httpx.AsyncClient`` and ``Celery.__init__`` for deterministic behavior.
    Call history is reset per-test by ``_reset_session_mocks``.

Environment Variables
---------------------
- ``EXEGESIS_SKIP_HEAVY_FIXTURES=1``: Skip loading mocks.py fixtures.
- ``EXEGESIS_MEMCHECK=1``: Enable per-test memory leak detection.
- ``EXEGESIS_ALLOW_INSECURE_STARTUP=1``: Allow insecure startup (set by default in tests).
- ``EXEGESIS_TESTING=1``: Signal test mode to application code.
"""

from __future__ import annotations

import asyncio
import contextlib
from contextvars import ContextVar
import gc
import hashlib
import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import inspect
import io
import json
import logging
import os
import socket
import sys
import types
import warnings
from collections.abc import Callable, Generator, Iterable, Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, patch

from urllib.request import OpenerDirector, Request

if TYPE_CHECKING:  # pragma: no cover - imported only for type checking
    from exegesis.adapters import AdapterRegistry
    from exegesis.application import ApplicationContainer
    from tests.fixtures import RegressionDataFactory
    from testcontainers.postgres import PostgresContainer

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Lazy Stub Meta Path Finder - Defers stub creation until actually imported
# ---------------------------------------------------------------------------
class _LazyStubFinder(importlib.abc.MetaPathFinder):
    """Defer stub module creation until first import attempt.

    This avoids creating ~10 stub modules at conftest load time when they're
    not needed, saving 20-50ms on initial collection.
    """

    _STUB_BUILDERS: dict[str, Callable[[], types.ModuleType]] = {}
    _installed = False

    @classmethod
    def register_stub(cls, module_name: str, builder: Callable[[], types.ModuleType]) -> None:
        """Register a builder for a stub module."""
        cls._STUB_BUILDERS[module_name] = builder

    @classmethod
    def install(cls) -> None:
        """Install the finder in sys.meta_path if not already installed."""
        if cls._installed:
            return
        # Insert after the normal finders but before any other meta path hooks
        sys.meta_path.insert(len(sys.meta_path), cls())
        cls._installed = True

    def find_spec(
        self,
        fullname: str,
        path: Any,
        target: Any = None,
    ) -> importlib.machinery.ModuleSpec | None:
        """Return a spec for stubbed modules when real import fails."""
        root_module = fullname.split(".")[0]

        # Only handle modules we have stubs for
        if root_module not in self._STUB_BUILDERS:
            return None

        # Check if real module exists - if so, let normal import handle it
        if importlib.util.find_spec(fullname) is not None:
            return None

        # Create stub on demand
        return importlib.machinery.ModuleSpec(
            fullname,
            _LazyStubLoader(self._STUB_BUILDERS[root_module]),
            is_package=(fullname == root_module),
        )


class _LazyStubLoader(importlib.abc.Loader):
    """Loader that creates stub modules on demand."""

    def __init__(self, builder: Callable[[], types.ModuleType]) -> None:
        self._builder = builder
        self._module: types.ModuleType | None = None

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> types.ModuleType | None:
        if self._module is None:
            self._module = self._builder()
        return self._module

    def exec_module(self, module: types.ModuleType) -> None:
        pass


# ---------------------------------------------------------------------------
# Collection Fingerprint Cache - Skip re-collection when tests haven't changed
# ---------------------------------------------------------------------------
_COLLECTION_CACHE_FILE = PROJECT_ROOT / ".pytest_cache" / "v" / "collection_fingerprint.json"


# Cache the test fingerprint to avoid recomputing during the same session
_cached_fingerprint: str | None = None


def _compute_test_fingerprint(test_root: Path, *, force: bool = False) -> str:
    """Compute a hash of test file mtimes for cache invalidation.

    Results are cached for the duration of the session to avoid repeated
    filesystem traversal.
    """
    global _cached_fingerprint
    if _cached_fingerprint is not None and not force:
        return _cached_fingerprint

    hasher = hashlib.md5(usedforsecurity=False)
    try:
        for py_file in sorted(test_root.rglob("*.py")):
            if "__pycache__" in str(py_file):
                continue
            stat = py_file.stat()
            hasher.update(f"{py_file}:{stat.st_mtime_ns}".encode())
    except Exception:
        # Any error means we can't trust the cache
        return ""
    _cached_fingerprint = hasher.hexdigest()
    return _cached_fingerprint


def _load_collection_cache(config: "pytest.Config") -> list[str] | None:
    """Load cached collection if fingerprint matches."""
    if not config.getoption("--use-collection-cache", default=False):
        return None

    try:
        if not _COLLECTION_CACHE_FILE.exists():
            return None

        cache_data = json.loads(_COLLECTION_CACHE_FILE.read_text())
        current_fingerprint = _compute_test_fingerprint(PROJECT_ROOT / "tests")

        if cache_data.get("fingerprint") != current_fingerprint:
            return None

        return cache_data.get("items", [])
    except Exception:
        return None


def _save_collection_cache(items: list["pytest.Item"], *, enabled: bool) -> None:
    """Save collection cache with fingerprint.

    Args:
        items: Test items to cache.
        enabled: Only save if caching is enabled (avoids unnecessary I/O).
    """
    if not enabled:
        return

    try:
        fingerprint = _compute_test_fingerprint(PROJECT_ROOT / "tests")
        if not fingerprint:
            return

        _COLLECTION_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _COLLECTION_CACHE_FILE.write_text(json.dumps({
            "fingerprint": fingerprint,
            "items": [item.nodeid for item in items],
        }))
    except Exception:
        pass  # Cache save failure is non-fatal


def _install_optional_dependency_stubs() -> None:
    """Install stubs for optional dependencies to allow collection without them."""

    # 1. Ensure Celery is available (either real or stubbed)
    try:
        import celery
    except ImportError:
        # Create a minimal Celery stub package
        celery = types.ModuleType("celery")
        celery.__path__ = []  # Mark as package

        # Stub main Celery class
        class CeleryStub:
            def __init__(self, *args, **kwargs):
                self.conf = types.SimpleNamespace(
                    task_always_eager=True,
                    task_eager_propagates=True,
                    broker_url="memory://",
                    result_backend="memory://",
                    beat_schedule={},
                )

            def task(self, *args, **kwargs):
                def decorator(func):
                    func.delay = lambda *a, **k: func(*a, **k)
                    return func
                return decorator

        celery.Celery = CeleryStub  # type: ignore

        # Stub exceptions
        celery.exceptions = types.ModuleType("celery.exceptions")
        class Retry(Exception):
            pass
        celery.exceptions.Retry = Retry  # type: ignore

        # Stub schedules
        celery.schedules = types.ModuleType("celery.schedules")
        celery.schedules.crontab = lambda **k: k

        # Stub utils.log
        celery.utils = types.ModuleType("celery.utils")
        celery.utils.log = types.ModuleType("celery.utils.log")
        celery.utils.log.get_task_logger = lambda name: logging.getLogger(name)

        sys.modules["celery"] = celery
        sys.modules["celery.exceptions"] = celery.exceptions
        sys.modules["celery.schedules"] = celery.schedules
        sys.modules["celery.utils"] = celery.utils
        sys.modules["celery.utils.log"] = celery.utils.log

    # 2. Ensure celery.contrib.pytest is available
    try:
        import celery.contrib.pytest
    except ImportError:
        # Try to load from local repo if possible
        local_plugin = PROJECT_ROOT / "celery" / "contrib" / "pytest.py"
        if local_plugin.exists():
            spec = importlib.util.spec_from_file_location("celery.contrib.pytest", str(local_plugin))
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules["celery.contrib.pytest"] = module
                spec.loader.exec_module(module)

    # 3. FastAPI Stub
    try:
        import fastapi
    except ImportError:
        fastapi = types.ModuleType("fastapi")
        fastapi.status = types.SimpleNamespace(HTTP_422_UNPROCESSABLE_CONTENT=422)
        sys.modules["fastapi"] = fastapi
        sys.modules["fastapi.status"] = fastapi.status

    # 4. Workers Tasks Stub
    # If workers module exists but tasks fails to import (due to missing deps), stub it
    workers_module = "exegesis.infrastructure.api.app.workers.tasks"
    if workers_module not in sys.modules:
        try:
            importlib.import_module(workers_module)
        except Exception:
            # Create stub for tasks module
            tasks = types.ModuleType(workers_module)

            class CeleryConfStub:
                def __init__(self):
                    self.task_always_eager = True
                    self.task_eager_propagates = True
                    self.broker_url = "memory://"
                    self.result_backend = "memory://"
                    self.task_ignore_result = False
                    self.task_store_eager_result = False

                def update(self, **kwargs):
                    for k, v in kwargs.items():
                        setattr(self, k, v)

            tasks.celery = types.SimpleNamespace(
                conf=CeleryConfStub()
            )
            sys.modules[workers_module] = tasks

            # Register in parent
            try:
                parent = importlib.import_module("exegesis.infrastructure.api.app.workers")
                setattr(parent, "tasks", tasks)
            except ImportError:
                pass

_install_optional_dependency_stubs()


_EXAMPLE_COM_RESPONSES: dict[str, str] = {
    "https://example.com/test": "<html><body>Test fixture</body></html>",
    "https://example.com/job-test": "<html><body>Job fixture</body></html>",
    "https://example.com/timing": "<html><body>Timing check</body></html>",
    "https://example.com/benchmark": "<html><body>Benchmark check</body></html>",
    "https://example.com/fixture": "<html><body>Retry fixture</body></html>",
    "https://example.com/replay": "<html><body>Replay fixture</body></html>",
}


# Unified suite configuration - drives CLI options, collection filtering, and fixture injection
_SUITE_CONFIG: dict[str, dict[str, Any]] = {
    "schema": {
        "flag": "--schema",
        "help": "Enable schema-dependent tests (implied by --pgvector).",
        "implies": [],
        "directories": {"db", "integration"},  # Skip these dirs when flag not set
        "fixtures": ["schema_isolation"],  # Auto-inject these fixtures
    },
    "pgvector": {
        "flag": "--pgvector",
        "help": "Enable tests requiring a Postgres+pgvector container (implies --schema).",
        "implies": ["schema"],
        "directories": {"pgvector", "ingest"},
        "fixtures": ["pgvector_db"],
    },
    "contract": {
        "flag": "--contract",
        "help": "Enable contract tests validating API schemas.",
        "implies": [],
        "directories": {"contracts"},
        "fixtures": [],
    },
    "gpu": {
        "flag": "--gpu",
        "help": "Enable tests requiring GPU acceleration.",
        "implies": [],
        "directories": {"gpu"},
        "fixtures": [],
    },
    "redteam": {
        "flag": "--redteam",
        "help": "Enable adversarial LLM guardrail security tests.",
        "implies": [],
        "directories": {"redteam"},
        "fixtures": [],
    },
    "performance": {
        "flag": "--performance",
        "help": "Enable performance regression tests with timing assertions.",
        "implies": [],
        "directories": {"perf"},
        "fixtures": [],
    },
}


class _ExampleComHeaders(dict):
    """Mimic the header API used by urllib responses."""

    def get_content_charset(self) -> str | None:  # pragma: no cover - simple helper
        content_type = self.get("Content-Type")
        if not content_type:
            return None
        if "charset=" in content_type:
            return content_type.split("charset=", 1)[1].split(";", 1)[0].strip()
        return None


class _ExampleComResponse:
    """Deterministic HTTP response used to stub example.com fetches."""

    def __init__(self, url: str, html: str) -> None:
        self._url = url
        self._body = html.encode("utf-8")
        self._cursor = 0
        self.headers = _ExampleComHeaders(
            {
                "Content-Length": str(len(self._body)),
                "Content-Type": "text/html; charset=utf-8",
            }
        )

    def read(self, size: int | None = -1) -> bytes:
        if size is None or size < 0:
            size = len(self._body) - self._cursor
        if self._cursor >= len(self._body):
            return b""
        end = min(len(self._body), self._cursor + size)
        chunk = self._body[self._cursor:end]
        self._cursor = end
        return bytes(chunk)

    def geturl(self) -> str:
        return self._url

    def close(self) -> None:  # pragma: no cover - compatibility no-op
        pass


@pytest.fixture(autouse=True)
def stub_example_com_requests(monkeypatch: pytest.MonkeyPatch):
    """Stub out external network access for example.com URLs during tests."""

    from urllib.error import HTTPError

    original_open = OpenerDirector.open

    def _open(self, fullurl, data=None, timeout=socket._GLOBAL_DEFAULT_TIMEOUT):  # type: ignore[override]
        url = fullurl
        if isinstance(fullurl, Request):
            url = fullurl.full_url
        elif hasattr(fullurl, "full_url"):
            url = fullurl.full_url

        if isinstance(url, bytes):
            url = url.decode("utf-8", errors="ignore")

        if isinstance(url, str) and url.startswith("https://example.com/"):
            html = _EXAMPLE_COM_RESPONSES.get(url)
            if html is None:
                raise HTTPError(url, 404, "Not Found", {}, None)
            return _ExampleComResponse(url, html)

        return original_open(self, fullurl, data, timeout)

    monkeypatch.setattr(OpenerDirector, "open", _open)
    yield


class _DowngradeIngestionErrorFilter(logging.Filter):
    """Re-label expected ingestion errors as warnings for clearer test output."""

    def filter(self, record: logging.LogRecord) -> bool:  # pragma: no cover - logging glue
        if record.getMessage().startswith("Failed to process URL ingestion"):
            record.levelno = logging.WARNING
            record.levelname = "WARNING"
        return True


@pytest.fixture(scope="session", autouse=True)
def downgrade_ingestion_error_logs():
    """Suppress noisy ingestion failure errors emitted during retry scenarios."""

    logger = logging.getLogger("exegesis.infrastructure.api.app.workers.tasks")
    flt = _DowngradeIngestionErrorFilter()
    logger.addFilter(flt)
    try:
        yield
    finally:
        logger.removeFilter(flt)
_EMBEDDING_MODULE_NAME = "exegesis.infrastructure.api.app.library.ingest.embeddings"


class _BootstrapEmbeddingServiceStub:
    """Lightweight embedding backend used in bootstrap-oriented tests."""

    def __init__(self, dimension: int = 768) -> None:
        self._dimension = dimension
        self.embed_calls: list[tuple[tuple[str, ...], int]] = []
        self.clear_cache_calls = 0

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: Iterable[str], *, batch_size: int) -> list[list[float]]:
        normalised = tuple(str(text) for text in texts)
        self.embed_calls.append((normalised, batch_size))
        return [
            [float(index + 1)] * self._dimension for index, _ in enumerate(normalised)
        ]

    def clear_cache(self) -> None:
        self.clear_cache_calls += 1

    def reset(self) -> None:
        """Reset call tracking for test isolation."""
        self.embed_calls.clear()
        self.clear_cache_calls = 0


# Session-scoped to avoid repeated imports of the embeddings module
@pytest.fixture(scope="session")
def _embedding_stub_session() -> _BootstrapEmbeddingServiceStub:
    """Create a shared bootstrap embedding service stub."""
    from exegesis.application.facades.settings import get_settings

    settings = get_settings()
    stub = _BootstrapEmbeddingServiceStub(dimension=settings.embedding_dim)
    return stub


@pytest.fixture(autouse=True)
def _bootstrap_embedding_service_stub(
    _embedding_stub_session: _BootstrapEmbeddingServiceStub,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[_BootstrapEmbeddingServiceStub]:
    """Patch bootstrap to provide a deterministic embedding service stub."""
    stub = _embedding_stub_session
    stub.reset()  # Clear call history from previous test
    embeddings_module = importlib.import_module(_EMBEDDING_MODULE_NAME)
    monkeypatch.setattr(
        embeddings_module,
        "get_embedding_service",
        lambda: stub,
        raising=False,
    )
    from exegesis.infrastructure.api.app.library.ingest import adapters as ingest_adapters

    ingest_adapters.ensure_embedding_rebuild_adapters_registered()
    yield stub


@pytest.fixture
def bootstrap_embedding_service_stub(
    _bootstrap_embedding_service_stub: _BootstrapEmbeddingServiceStub,
) -> _BootstrapEmbeddingServiceStub:
    """Return the bootstrap embedding service stub for explicit assertions."""
    return _bootstrap_embedding_service_stub



try:  # pragma: no cover - optional dependency
    import pydantic  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - lightweight CI environments
    pydantic = types.ModuleType("pydantic")  # type: ignore[assignment]
    sys.modules["pydantic"] = pydantic

if not hasattr(pydantic, "BaseModel"):
    class _BaseModel:
        def __init__(self, **_kwargs: object) -> None:
            pass

    pydantic.BaseModel = _BaseModel  # type: ignore[attr-defined]


def _identity_decorator(*_args: object, **_kwargs: object):  # pragma: no cover - helper
    def _decorator(func: Any) -> Any:
        return func

    return _decorator


if not hasattr(pydantic, "Field"):
    def _field(*_args: object, **_kwargs: object) -> None:
        return None

    pydantic.Field = _field  # type: ignore[attr-defined]

if not hasattr(pydantic, "field_validator"):
    pydantic.field_validator = _identity_decorator  # type: ignore[attr-defined]

if not hasattr(pydantic, "model_validator"):
    pydantic.model_validator = _identity_decorator  # type: ignore[attr-defined]

if not hasattr(pydantic, "AliasChoices"):
    class _AliasChoices:
        def __init__(self, *_choices: object) -> None:
            self.choices = _choices

    pydantic.AliasChoices = _AliasChoices  # type: ignore[attr-defined]

if not hasattr(pydantic, "model_serializer"):
    pydantic.model_serializer = _identity_decorator  # type: ignore[attr-defined]

if "pydantic_settings" not in sys.modules:  # pragma: no cover - lightweight CI environments
    spec = importlib.util.find_spec("pydantic_settings")
    if spec is None:
        pydantic_settings = types.ModuleType("pydantic_settings")

        class _BaseSettings:
            model_config: dict[str, object] = {}

            def __init__(self, **_kwargs: object) -> None:
                pass

        pydantic_settings.BaseSettings = _BaseSettings  # type: ignore[attr-defined]
        pydantic_settings.SettingsConfigDict = dict  # type: ignore[attr-defined]

        sys.modules["pydantic_settings"] = pydantic_settings

try:  # pragma: no cover - optional dependency for integration fixtures
    import sqlalchemy
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import Connection, Engine
    from sqlalchemy.orm import Session, sessionmaker
    try:
        event = sqlalchemy.event
    except AttributeError:  # pragma: no cover - minimal SQLAlchemy stubs
        event = importlib.import_module("sqlalchemy.event")
except (ModuleNotFoundError, ImportError):  # pragma: no cover - allows running lightweight suites
    create_engine = None  # type: ignore[assignment]
    text = None  # type: ignore[assignment]
    Connection = object  # type: ignore[assignment]
    Engine = object  # type: ignore[assignment]
    Session = object  # type: ignore[assignment]
    sessionmaker = None  # type: ignore[assignment]
    class _EventStub:  # pragma: no cover - lightweight environments skip DB tests
        @staticmethod
        def listens_for(*_args: object, **_kwargs: object):
            def _decorator(func):
                return func

            return _decorator

        @staticmethod
        def remove(*_args: object, **_kwargs: object) -> None:
            return None

    event = _EventStub()  # type: ignore[assignment]

try:  # pragma: no cover - factory depends on optional domain extras
    from tests.factories.application import isolated_application_container
    from tests.fixtures.pgvector import (
        PGVectorDatabase,
        PGVectorClone,
        provision_pgvector_database,
    )
except ModuleNotFoundError as exc:  # pragma: no cover - light environments
    isolated_application_container = None  # type: ignore[assignment]
    _APPLICATION_FACTORY_IMPORT_ERROR = exc
else:
    _APPLICATION_FACTORY_IMPORT_ERROR: ModuleNotFoundError | None = None


_SQLALCHEMY_AVAILABLE = create_engine is not None

if not _SQLALCHEMY_AVAILABLE:

    def _sqlalchemy_missing(*_args: object, **_kwargs: object):  # type: ignore[misc]
        pytest.skip("sqlalchemy not installed")

    create_engine = _sqlalchemy_missing  # type: ignore[assignment]
    text = _sqlalchemy_missing  # type: ignore[assignment]


def _require_application_factory() -> None:
    if isolated_application_container is None:
        reason = _APPLICATION_FACTORY_IMPORT_ERROR or ModuleNotFoundError("pythonbible")
        pytest.skip(f"application factory unavailable: {reason}")

pytest_plugins: list[str] = ["celery.contrib.pytest"]

# Conditionally load heavy fixtures based on environment
_SKIP_HEAVY = os.environ.get("EXEGESIS_SKIP_HEAVY_FIXTURES", "0") in {"1", "true", "TRUE"}

# Check if real pydantic is installed (not just our stub) for heavy fixtures
_REAL_PYDANTIC_AVAILABLE = importlib.util.find_spec("pydantic") is not None

if not _SKIP_HEAVY:
    if not _REAL_PYDANTIC_AVAILABLE:  # pragma: no cover - exercised in lightweight envs
        warnings.warn(
            "pydantic not installed; skipping heavy pytest fixtures that depend on it.",
            RuntimeWarning,
        )
    else:
        pytest_plugins.append("tests.fixtures.mocks")
        # Note: tests/fixtures/heavy.py contains extracted heavy fixtures for future
        # refactoring. Currently, heavy fixtures remain in this file for compatibility.
        # To use the separated heavy fixtures, manually add to pytest_plugins:
        # pytest_plugins.append("tests.fixtures.heavy")

try:  # pragma: no cover - optional dependency in local test harness
    import pytest_cov  # type: ignore  # noqa: F401

    _HAS_PYTEST_COV = True
except ModuleNotFoundError:  # pragma: no cover - executed when plugin is missing
    _HAS_PYTEST_COV = False

try:  # pragma: no cover - psutil optional for lightweight environments
    import psutil
except ModuleNotFoundError:  # pragma: no cover - allows running without psutil
    psutil = None  # type: ignore[assignment]
    _PSUTIL_PROCESS = None
else:  # pragma: no cover - process lookup can fail in sandboxes
    try:
        _PSUTIL_PROCESS = psutil.Process()
    except Exception:
        _PSUTIL_PROCESS = None

_ENABLE_MEMCHECK = os.getenv("EXEGESIS_MEMCHECK", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

_SCHEMA_CONNECTION: ContextVar[Connection | None] = ContextVar("_SCHEMA_CONNECTION")


def _register_randomly_plugin(pluginmanager: pytest.PluginManager) -> bool:
    """Ensure pytest-randomly is registered when available."""

    if pluginmanager.hasplugin("randomly"):
        return True

    try:
        plugin_module = importlib.import_module("pytest_randomly.plugin")
    except ModuleNotFoundError:
        return False

    pluginmanager.register(plugin_module, "pytest_randomly")
    return True


def _register_xdist_plugin(pluginmanager: pytest.PluginManager) -> bool:
    """Ensure pytest-xdist is eagerly registered when the dependency exists."""

    if pluginmanager.hasplugin("xdist"):
        return True

    try:
        plugin_module = importlib.import_module("xdist.plugin")
    except ModuleNotFoundError:
        return False

    pluginmanager.register(plugin_module, "xdist")
    return True


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool:
    """Skip heavy test directories based on --fast mode and suite flags.

    This provides early filtering before AST parsing, saving significant time
    when running subsets of the test suite.
    """
    is_fast = config.getoption("--fast", default=False)
    is_collect_only = config.option.collect_only if hasattr(config.option, "collect_only") else False

    # --fast mode: skip heavy test directories entirely
    if is_fast:
        fast_skip_dirs = {
            "api",
            "integration",
            "ingest",
            "contracts",
            "workers",
            "redteam",
            "perf",
            "ranking",
            "e2e",
        }
        try:
            rel_path = collection_path.relative_to(config.rootpath / "tests")
            if rel_path.parts and rel_path.parts[0] in fast_skip_dirs:
                return True
        except ValueError:
            pass

    # Pre-filter by suite configuration: skip directories for disabled suites
    # This avoids parsing test files that will be skipped anyway
    if not is_collect_only:  # Don't filter during --collect-only to show full tree
        try:
            rel_path = collection_path.relative_to(config.rootpath / "tests")
            if rel_path.parts:
                first_part = rel_path.parts[0]
                for marker, conf in _SUITE_CONFIG.items():
                    if not config.getoption(marker, default=False):
                        if first_part in conf.get("directories", set()):
                            return True
        except ValueError:
            pass

    return False


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register optional CLI flags and shim coverage arguments when needed."""

    parser.addoption(
        "--fast",
        action="store_true",
        default=False,
        help="Skip heavy integration tests and use stubs for faster collection/execution.",
    )
    parser.addoption(
        "--use-collection-cache",
        action="store_true",
        default=False,
        help="Use cached test collection when source files haven't changed.",
    )

    if not _HAS_PYTEST_COV:
        group = parser.getgroup("cov", "coverage reporting (stub)")
        group.addoption(
            "--cov",
            action="append",
            default=[],
            dest="cov_source",
            metavar="PATH",
            help="Stub option allowing tests to run without pytest-cov installed.",
        )
        group.addoption(
            "--cov-report",
            action="append",
            default=[],
            dest="cov_report",
            metavar="TYPE",
            help="Stub option allowing tests to run without pytest-cov installed.",
        )
        group.addoption(
            "--cov-fail-under",
            action="store",
            default=None,
            dest="cov_fail_under",
            type=float,
            help="Stub option allowing tests to run without pytest-cov installed.",
        )

    for marker, config in _SUITE_CONFIG.items():
        parser.addoption(
            config["flag"],
            action="store_true",
            default=False,
            dest=marker,
            help=config["help"],
        )


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers and configure optional plugins.

    This hook centralizes plugin configuration that was previously handled
    by run_tests.py, enabling direct ``pytest`` invocation with identical
    behavior.
    """

    # --collect-only fast path: skip heavy fixture setup for faster discovery
    is_collect_only = getattr(config.option, "collect_only", False)
    if is_collect_only:
        os.environ["EXEGESIS_SKIP_HEAVY_FIXTURES"] = "1"

    # Handle implications: e.g. --pgvector implies --schema
    for marker, conf in _SUITE_CONFIG.items():
        if config.getoption(marker):
            for implied in conf["implies"]:
                setattr(config.option, implied, True)

    is_fast = config.getoption("--fast", default=False)

    # Configure pytest-timeout if available (previously in run_tests.py)
    if config.pluginmanager.hasplugin("timeout"):
        if not hasattr(config.option, "timeout") or config.option.timeout is None:
            config.option.timeout = 60

    # Configure pytest-randomly seed (plugin already registered in pytest_load_initial_conftests)
    if config.pluginmanager.hasplugin("randomly"):
        config.option.randomly_seed = 1337

    # In fast mode, unregister xdist to avoid startup overhead
    if is_fast and config.pluginmanager.hasplugin("xdist"):
        with contextlib.suppress(ValueError):
            config.pluginmanager.unregister(name="xdist")

    config.addinivalue_line(
        "markers",
        "asyncio: mark a test function as running with an asyncio event loop.",
    )
    config.addinivalue_line(
        "markers",
        "allow_sleep: opt out of the session-wide sleep patches for a test.",
    )
    config.addinivalue_line(
        "markers",
        "memcheck: enable the manage_memory fixture for targeted leak hunts.",
    )

    # Register suite markers from configuration
    for marker, conf in _SUITE_CONFIG.items():
        config.addinivalue_line("markers", f"{marker}: {conf['help']}")

    config.addinivalue_line(
        "markers",
        "reset_state: reset global facade state before/after test (database, settings, telemetry).",
    )


def _get_usefixtures(item: pytest.Item) -> set[str]:
    """Extract all fixture names from usefixtures markers on an item."""
    fixtures: set[str] = set()
    for marker in item.iter_markers(name="usefixtures"):
        for arg in marker.args:
            fixtures.add(arg)
    return fixtures


def _get_xdist_groups(item: pytest.Item) -> set[str]:
    """Extract all xdist group names from an item."""
    return {
        marker.kwargs.get("name")
        for marker in item.iter_markers(name="xdist_group")
        if marker.kwargs.get("name")
    }


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip tests that require disabled suite options and apply auto-fixtures.

    Uses batched marker operations for improved performance.
    """
    # Build skip markers for disabled suites
    skip_markers: dict[str, pytest.Mark] = {}
    enabled_suites: set[str] = set()
    for marker, conf in _SUITE_CONFIG.items():
        if config.getoption(marker):
            enabled_suites.add(marker)
        else:
            skip_markers[marker] = pytest.mark.skip(reason=f"requires {conf['flag']} flag")

    has_xdist = config.pluginmanager.hasplugin("xdist")

    # Process items with batched marker operations
    for item in items:
        markers_to_add: list[pytest.Mark] = []

        # 1. Apply skip markers for disabled suites
        for marker, skip_mark in skip_markers.items():
            if marker in item.keywords:
                markers_to_add.append(skip_mark)

        # 2. Auto-inject fixtures for enabled suites
        existing_fixtures = _get_usefixtures(item)
        for suite in enabled_suites:
            if suite in item.keywords:
                for fixture in _SUITE_CONFIG[suite].get("fixtures", []):
                    if fixture not in existing_fixtures:
                        markers_to_add.append(pytest.mark.usefixtures(fixture))
                        existing_fixtures.add(fixture)

        # 3. Handle special markers (memcheck, reset_state)
        if not _ENABLE_MEMCHECK and item.get_closest_marker("memcheck"):
            if "manage_memory" not in existing_fixtures:
                markers_to_add.append(pytest.mark.usefixtures("manage_memory"))

        if item.get_closest_marker("reset_state"):
            if "reset_global_state" not in existing_fixtures:
                markers_to_add.append(pytest.mark.usefixtures("reset_global_state"))

        # 4. xdist grouping - group by module path for locality
        if has_xdist:
            path_str = str(item.path)
            if path_str not in _get_xdist_groups(item):
                markers_to_add.append(pytest.mark.xdist_group(name=path_str))

        # Apply all markers at once
        for marker in markers_to_add:
            item.add_marker(marker)

    # Save collection cache for future runs (only if caching is enabled)
    _save_collection_cache(items, enabled=config.getoption("--use-collection-cache", default=False))


def pytest_load_initial_conftests(
    early_config: pytest.Config, parser: pytest.Parser, args: list[str]
) -> None:
    """Ensure required plugins are available before parsing ini options.

    Note: Sequential imports are used since ThreadPoolExecutor overhead exceeds
    any benefit for just 2 small plugin modules.
    """
    pluginmanager = early_config.pluginmanager

    # Register pytest-randomly if available (for deterministic test ordering)
    _register_randomly_plugin(pluginmanager)

    # Register pytest-xdist if available (for parallel execution)
    # Only register here if not in --fast mode (checked later in configure)
    _register_xdist_plugin(pluginmanager)


@pytest.fixture
def regression_factory():
    """Provide a seeded factory for synthesising regression datasets."""

    try:
        from tests.fixtures import (  # type: ignore
            REGRESSION_FIXTURES_AVAILABLE,
            REGRESSION_IMPORT_ERROR,
            RegressionDataFactory,
        )
    except ModuleNotFoundError as exc:  # pragma: no cover - thin local envs
        pytest.skip(f"faker not installed for regression factory: {exc}")
    except Exception as exc:  # pragma: no cover - guard against optional deps
        pytest.skip(f"regression fixtures unavailable: {exc}")
    if not REGRESSION_FIXTURES_AVAILABLE:
        reason = REGRESSION_IMPORT_ERROR or ModuleNotFoundError("unknown dependency")
        pytest.skip(f"regression fixtures unavailable: {reason}")
    return RegressionDataFactory()


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


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> bool | None:
    """Execute ``async def`` tests without requiring pytest-asyncio."""

    if not inspect.iscoroutinefunction(pyfuncitem.obj):
        return None

    if pyfuncitem.get_closest_marker("asyncio") is None:
        return None

    testargs = {
        name: pyfuncitem.funcargs[name]
        for name in pyfuncitem._fixtureinfo.argnames  # type: ignore[attr-defined]
        if name in pyfuncitem.funcargs
    }
    asyncio.run(pyfuncitem.obj(**testargs))
    return True


os.environ.setdefault("EXEGESIS_ALLOW_INSECURE_STARTUP", "1")
os.environ.setdefault("EXEGESIS_ENVIRONMENT", "development")


@pytest.fixture(scope="session", autouse=True)
def _configure_celery_for_tests() -> Generator[None, None, None]:
    """Execute Celery tasks inline to avoid external broker dependencies."""

    os.environ.setdefault("EXEGESIS_TESTING", "1")

    try:
        from exegesis.infrastructure.api.app.workers import tasks as worker_tasks
    except Exception:  # pragma: no cover - Celery optional in some test subsets
        yield
        return

    app = worker_tasks.celery
    previous_config = {
        "task_always_eager": app.conf.task_always_eager,
        "task_eager_propagates": app.conf.task_eager_propagates,
        "task_ignore_result": getattr(app.conf, "task_ignore_result", False),
        "task_store_eager_result": getattr(app.conf, "task_store_eager_result", False),
        "broker_url": app.conf.broker_url,
        "result_backend": app.conf.result_backend,
    }

    app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
        task_ignore_result=True,
        task_store_eager_result=False,
        broker_url="memory://",
        result_backend=None,
    )

    try:
        yield
    finally:
        app.conf.update(**previous_config)


POSTGRES_IMAGE = os.environ.get("PYTEST_PGVECTOR_IMAGE", "pgvector/pgvector:pg15")


@pytest.fixture(scope="session")
def pgvector_db(request: pytest.FixtureRequest) -> Iterator[PGVectorDatabase]:
    """Provision a seeded Postgres+pgvector database for heavy integration suites.

    The fixture starts a single Testcontainer for the duration of the test
    session, applies the project's SQL migrations, and seeds the bundled
    reference datasets.  Individual tests can call ``clone_database`` on the
    returned object to create isolated databases that inherit the prepared
    schema and extensions without incurring the full migration cost again.
    """

    if not request.config.getoption("pgvector"):
        pytest.skip("requires --pgvector flag")

    try:
        context = provision_pgvector_database(image=POSTGRES_IMAGE)
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        pytest.skip(f"testcontainers not installed: {exc}")
    try:
        with context as database:
            yield database
    except ModuleNotFoundError as exc:  # pragma: no cover - container provisioning
        pytest.skip(f"testcontainers not installed: {exc}")
    except Exception as exc:  # pragma: no cover - surfaced when Docker unavailable
        pytest.skip(f"Unable to start Postgres Testcontainer: {exc}")


@pytest.fixture(scope="session")
def pgvector_container(pgvector_db: PGVectorDatabase) -> PostgresContainer:
    """Return the underlying Testcontainer for backwards-compatible fixtures."""

    return pgvector_db.container


@pytest.fixture(scope="session")
def pgvector_database_url(pgvector_db: PGVectorDatabase) -> str:
    """Expose the SQLAlchemy URL for the seeded pgvector template database."""

    return pgvector_db.url


@pytest.fixture(scope="session")
def pgvector_engine(pgvector_db: PGVectorDatabase) -> Iterator[Engine]:
    """Yield an engine connected to the seeded pgvector template database."""

    engine = pgvector_db.create_engine()
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def pgvector_migrated_database_url(pgvector_db: PGVectorDatabase) -> str:
    """Return the URL of the migrated pgvector database (for legacy callers)."""

    return pgvector_db.url


def _initialise_shared_database(db_path: Path) -> str:
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


def _sqlite_database_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """Create a SQLite database URL with migrations applied."""
    from exegesis.infrastructure.api.app.db import run_sql_migrations as migrations_module
    from exegesis.application.facades.database import Base

    database_dir = tmp_path_factory.mktemp("sqlite", numbered=True)
    path = database_dir / "test.db"
    url = f"sqlite:///{path}"

    # Create engine and apply migrations
    engine = create_engine(url, future=True)
    try:
        # First create all tables from models
        Base.metadata.create_all(bind=engine)

        # Temporarily disable performance indexes for SQLite (they may use PG-specific syntax)
        original_index_helper = getattr(
            migrations_module, "_ensure_performance_indexes", None
        )
        try:
            if original_index_helper is not None:
                migrations_module._ensure_performance_indexes = lambda _engine: []  # type: ignore[attr-defined]
            migrations_module.run_sql_migrations(engine)
        finally:
            if original_index_helper is not None:
                migrations_module._ensure_performance_indexes = original_index_helper  # type: ignore[attr-defined]
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
def ml_models() -> Callable[[str], Any]:
    """Load expensive ML models lazily and cache them for reuse."""

    cache: dict[str, Any] = {}

    def _load(model_name: str, *, loader: Callable[[], Any] | None = None) -> Any:
        if model_name not in cache:
            if loader is not None:
                cache[model_name] = loader()
            else:
                cache[model_name] = _load_model_from_registry(model_name)
        return cache[model_name]

    return _load


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

    The fixture yields SQLAlchemy-compatible URLs so that test suites can
    ``create_engine`` with minimal boilerplate.
    """

    if request.config.getoption("pgvector"):
        pgvector_url = request.getfixturevalue("pgvector_migrated_database_url")
        yield pgvector_url
        return

    yield from _sqlite_database_url(tmp_path_factory)


@pytest.fixture(scope="session")
def integration_engine(
    integration_database_url: str,
) -> Iterator[Engine]:
    """Provide a SQLAlchemy engine bound to the integration database."""

    engine = create_engine(integration_database_url, future=True)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(scope="function")
def db_transaction(integration_engine: Engine) -> Generator[Any, None, None]:
    """Wrap tests in a transaction that is rolled back afterwards."""

    connection = integration_engine.connect()
    transaction = connection.begin()
    try:
        yield connection
    finally:
        transaction.rollback()
        connection.close()


@pytest.fixture(scope="function")
def integration_session(request: pytest.FixtureRequest) -> Generator[Session, None, None]:
    """Return a SQLAlchemy ``Session`` bound to an isolated transaction."""

    if sessionmaker is None:  # pragma: no cover - lightweight envs without SQLAlchemy
        pytest.skip("sqlalchemy not installed")

    connection = _SCHEMA_CONNECTION.get(None)
    if connection is None:
        db_transaction = request.getfixturevalue("db_transaction")
        connection = cast("Connection", db_transaction)
    else:
        connection = cast("Connection", connection)

    SessionFactory = sessionmaker(bind=connection, future=True)  # type: ignore[arg-type]
    session = SessionFactory()
    nested = session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess: Session, transaction) -> None:  # type: ignore[no-redef]
        if transaction.nested and not transaction._parent.nested:  # pragma: no branch - mirrored from SQLAlchemy recipe
            sess.begin_nested()

    try:
        yield session
    finally:
        try:
            if nested.is_active:
                nested.rollback()
        except Exception:  # pragma: no cover - defensive cleanup
            pass
        event.remove(session, "after_transaction_end", _restart_savepoint)
        session.close()


@pytest.fixture(scope="function")
def schema_isolation(db_transaction: Any) -> Iterator[Any]:
    """Ensure ``@pytest.mark.schema`` tests automatically roll back state."""

    connection = cast("Connection", db_transaction)
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

    Several subsystems rely on the ``DATABASE_URL`` environment variable during
    initialisation. Setting it once per test session avoids repeated fixture
    setup work while still restoring any pre-existing value afterwards.

    Only activates when ``--schema`` or ``--pgvector`` flags are provided,
    avoiding expensive database setup for unit test runs.
    """
    # Skip database setup entirely for fast mode or when no schema tests are requested
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


@pytest.fixture(autouse=_ENABLE_MEMCHECK)
def manage_memory() -> Generator[None, None, None]:
    """Collect garbage eagerly and warn about potential leaks."""

    process = _PSUTIL_PROCESS
    before = process.memory_info().rss if process is not None else 0

    yield

    gc.collect()

    if process is None or before == 0:
        return

    after = process.memory_info().rss
    if after > before * 1.5:
        warnings.warn(
            "Potential memory leak detected in test execution",
            ResourceWarning,
            stacklevel=2,
        )


@pytest.fixture(scope="session", autouse=True)
def mock_sleep_session() -> dict[str, Any]:
    """Patch sleep functions once per session to minimise fixture churn."""

    async_sleep_mock = AsyncMock()
    time_patcher = patch("time.sleep", return_value=None)
    asyncio_patcher = patch("asyncio.sleep", new=async_sleep_mock)

    time_patcher.start()
    asyncio_patcher.start()
    try:
        yield {
            "time": time_patcher,
            "asyncio": asyncio_patcher,
            "async_mock": async_sleep_mock,
        }
    finally:
        asyncio_patcher.stop()
        time_patcher.stop()


@pytest.fixture(autouse=True)
def mock_sleep(request, mock_sleep_session: dict[str, Any]) -> Iterator[None]:
    patchers = mock_sleep_session
    async_mock: AsyncMock = patchers["async_mock"]

    if "allow_sleep" in request.keywords:
        time_patcher = patchers["time"]
        asyncio_patcher = patchers["asyncio"]
        asyncio_patcher.stop()
        time_patcher.stop()
        try:
            yield
        finally:
            time_patcher.start()
            asyncio_patcher.start()
            async_mock.reset_mock()
        return

    try:
        yield
    finally:
        async_mock.reset_mock()


class TestResourcePool:
    """Pool expensive resources for reuse across the test session."""

    def __init__(self) -> None:
        self._engines: dict[str, Engine] = {}

    def get_db_engine(self, url: str) -> Engine:
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


def _do_reset_global_state(*, skip_database: bool = False) -> None:
    """Reset all facade global state to prevent isolation issues.

    Args:
        skip_database: If True, don't reset database module state. This is used
            when the api_engine fixture has already set up database overrides.
    """
    # Import lazily to avoid circular imports during collection

    # 1. Reset database module state (unless skipped)
    if not skip_database:
        try:
            from exegesis.application.facades import database as database_module
        except ImportError:
            pass
        else:
            # Dispose any active engine to release file handles (important on Windows)
            if database_module._engine is not None:
                try:
                    database_module._engine.dispose()
                except Exception:
                    pass

            # Reset all global state
            database_module._engine = None
            database_module._SessionLocal = None
            database_module._engine_url_override = None

    # 2. Clear settings cache which may hold stale database URLs
    try:
        from exegesis.application.facades import settings as settings_module
        settings_module.get_settings.cache_clear()
        if hasattr(settings_module, "get_settings_cipher"):
            settings_module.get_settings_cipher.cache_clear()
    except Exception:
        pass

    # 3. Reset telemetry provider
    try:
        from exegesis.application.facades import telemetry as telemetry_module
        telemetry_module._provider = None
    except Exception:
        pass


@pytest.fixture
def reset_global_state(request: pytest.FixtureRequest) -> Generator[None, None, None]:
    """Reset all facade global state before and after each test.

    Use this fixture (or the ``@pytest.mark.reset_state`` marker) for tests that
    directly manipulate global singletons like ``database_module._engine`` and
    ``telemetry_module._provider``. This ensures those changes don't leak between
    tests by resetting state both before and after each test runs.

    Note: If the test uses the ``api_engine`` fixture, we skip resetting database
    state since that fixture manages its own database session override.
    """
    # Check if this test uses api_engine or api_test_client (which manages its own DB state)
    uses_api_engine = "api_engine" in request.fixturenames or "api_test_client" in request.fixturenames

    # Reset BEFORE test to ensure clean state
    # Skip database reset if api_engine will handle it
    _do_reset_global_state(skip_database=uses_api_engine)

    yield

    # Reset AFTER test to clean up
    # Always reset after, even if api_engine was used (it cleans up its own state)
    _do_reset_global_state()
