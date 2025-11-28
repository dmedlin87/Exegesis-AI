# Test Suite Refactoring Plan

> **Created**: 2025-11-24
> **Status**: Planning Phase
> **Estimated Effort**: 4-6 PRs over 2-3 weeks
> **Priority**: Medium-High (Developer Experience & CI Speed)

## Executive Summary

The test infrastructure has accumulated technical debt from rapid feature development. This plan addresses:

- **1,174-line root conftest.py** with 50+ fixtures and inline stubs
- **562-line api conftest.py** with extensive dependency stubbing
- **11+ test markers** creating fragmented test pyramid
- **Empty test directories** from removed features
- **Fixture duplication** across conftest files
- **Large monolithic test files** (some >40KB)

---

## Current State Analysis

### Root `tests/conftest.py` Problems

| Issue | Lines | Impact |
|-------|-------|--------|
| Inline Celery stub | 36-143 | 100+ lines of stub code |
| Pydantic stubs | 322-380 | Duplicated across files |
| SQLAlchemy optional handling | 381-409 | Complex conditional imports |
| HTTP response stubs | 147-251 | 100+ lines for example.com |
| Suite configuration | 157-178 | Clean but could be external |
| Database fixtures | 847-996 | 150+ lines of overlapping fixtures |

### `tests/api/conftest.py` Problems

| Issue | Lines | Impact |
|-------|-------|--------|
| FlagEmbedding stub | 20-38 | Simple but duplicated pattern |
| pypdf stub | 41-78 | Could be external module |
| OpenTelemetry stub | 81-119 | Could be external module |
| sklearn stubs | 122-262 | 140+ lines of stubs |
| External integration stubs | 286-345 | Session-scoped monkeypatching |
| Database fixture duplication | 475-562 | Overlaps with root fixtures |

### Test Directory Issues

```text
tests/
├── mcp_tools/        # EMPTY - MCP removal incomplete
├── platform/         # EMPTY - Platform events removed
├── case_builder/     # EMPTY - Unused
├── evidence/         # 8 items - May need audit
├── contracts/        # 1 item - Underutilized
└── api/              # 124 items - 85% of tests here
```

### Large Test Files (>10KB)

| File | Size | Recommendation |
|------|------|----------------|
| `test_ai_router.py` | 44KB | Split by workflow type |
| `test_ingest.py` | 37KB | Split by ingestion format |
| `test_ai_citation_export.py` | 22KB | Consider consolidation |
| `test_rag_guardrails.py` | 18KB | Keep as regression suite |
| `test_ai_watchlists.py` | 16KB | Keep as feature suite |
| `test_ai_registry.py` | 16KB | Keep as unit suite |

---

## Refactoring Plan

### Phase 1: Extract Stubs to Dedicated Modules (Week 1)

#### PR 1.1: Create `tests/stubs/` Package

Extract inline stubs to reusable modules:

```text
tests/stubs/
├── __init__.py           # Lazy import helpers
├── celery.py             # Celery stub + contrib.pytest
├── sklearn.py            # sklearn.* stubs
├── pypdf.py              # pypdf stubs
├── opentelemetry.py      # OTel tracer stubs
├── pydantic.py           # Pydantic fallbacks
├── flag_embedding.py     # FlagModel stub
└── sqlalchemy.py         # SQLAlchemy optional helpers
```

**Benefits:**

- Reduce root conftest.py by ~300 lines
- Reduce api conftest.py by ~200 lines
- Single source of truth for stub behavior
- Easier to maintain and update

**Migration Strategy:**

```python
# Before (in conftest.py)
class CeleryStub:
    def __init__(self, *args, **kwargs): ...

# After
from tests.stubs.celery import install_celery_stub
install_celery_stub()
```

#### PR 1.2: Consolidate HTTP Stubbing

Replace inline `_ExampleComResponse` with:

```python
# tests/stubs/http.py
from tests.stubs import install_http_stub

EXAMPLE_COM_RESPONSES = {
    "https://example.com/test": "<html>...</html>",
}

def install_http_stub(responses: dict[str, str] | None = None):
    """Install deterministic HTTP responses for test URLs."""
    ...
```

### Phase 2: Fixture Reorganization (Week 1-2)

#### PR 2.1: Create `tests/fixtures/database.py`

Consolidate database fixtures from both conftest files:

```python
# tests/fixtures/database.py

@pytest.fixture(scope="session")
def sqlite_template(tmp_path_factory) -> Path:
    """Session-scoped SQLite database with migrations applied."""
    ...

@pytest.fixture(scope="session")
def shared_engine(sqlite_template) -> Engine:
    """Shared engine connected to template database."""
    ...

@pytest.fixture
def db_session(shared_engine) -> Iterator[Session]:
    """Transaction-isolated session for each test."""
    ...
```

**Current Fixture Overlap:**

| Root conftest | API conftest | Proposed |
|---------------|--------------|----------|
| `shared_test_database` | `_api_engine_template` | `sqlite_template` |
| `integration_engine` | `_shared_api_engine` | `shared_engine` |
| `db_transaction` | `api_engine` | `db_session` |
| `integration_session` | - | `db_session` |

#### PR 2.2: Create `tests/fixtures/clients.py`

Extract test client fixtures:

```python
# tests/fixtures/clients.py

@pytest.fixture(scope="session")
def app_client() -> Iterator[TestClient]:
    """Session-scoped FastAPI test client."""
    from exegesis.infrastructure.api.app.main import app
    with TestClient(app) as client:
        yield client

@pytest.fixture
def api_client(db_session, app_client) -> TestClient:
    """Test client with isolated database transaction."""
    ...
```

### Phase 3: Test Marker Consolidation (Week 2)

#### PR 3.1: Marker Simplification

Implement the marker strategy from `PROJECT_IMPROVEMENTS_ROADMAP.md`:

| Current Markers | Action | Rationale |
|-----------------|--------|-----------|
| `db`, `pgvector`, `schema` | Merge → `integration` | All require DB |
| `slow` | Keep | Distinct timing concern |
| `celery` | Merge → `integration` | Celery uses eager mode |
| `e2e` | Keep | Full stack tests |
| `perf`, `performance` | Merge → `perf` | Duplicates |
| `gpu` | Keep | Hardware requirement |
| `contract` | Keep | API schema validation |
| `redteam` | Keep | Security testing |
| `flaky` | **Remove** | Fix or delete tests |

**New `_SUITE_CONFIG`:**

```python
_SUITE_CONFIG = {
    "integration": {
        "flag": "--integration",
        "help": "Enable integration tests (DB, migrations).",
        "implies": [],
        "aliases": ["--schema", "--db"],  # Backwards compat
    },
    "pgvector": {
        "flag": "--pgvector",
        "help": "Enable pgvector container tests.",
        "implies": ["integration"],
    },
    "slow": {
        "flag": "--slow",
        "help": "Enable slow tests (transformers, etc.).",
        "implies": [],
    },
    # ... remaining markers
}
```

#### PR 3.2: Remove Flaky Marker

1. Audit all `@pytest.mark.flaky` tests
2. Fix underlying issues or delete tests
3. Remove marker from `pyproject.toml`

### Suite/marker to refactor map (target state)

- **integration (db/schema)** – DB-backed tests in `tests/api`, `tests/ingest`, and parts of `tests/workers` that rely on real migrations.
  - **Primary fixtures:** `integration_engine`, `integration_session`, `db_transaction` → converge on `sqlite_template` / `shared_engine` / `db_session` in PR 2.1.
  - **PRs:** 2.1 (database fixtures), 2.2 (clients), 3.1 (marker aliases/flag wiring).
- **pgvector** – Heavy Postgres+pgvector tests (retrieval, ingestion, embeddings) using the Testcontainer.
  - **Primary fixtures:** `pgvector_db`, `pgvector_engine`, `integration_session`.
  - **PRs:** 2.1 (shared DB fixtures), 3.1 (implies `integration`), 4.1 (directory cleanup if any pgvector-only dirs are empty).
- **slow** – Long-running tests (LLM calls, full RAG/e2e scenarios).
  - **Primary areas:** `tests/api/test_ai_router.py`, `tests/api/test_rag_guardrails.py`, `tests/api/test_ai_watchlists.py`.
  - **PRs:** 5.1/5.2 (large-file splits), 3.1 (marker description only).
- **celery** – Worker/Celery tests that require the Celery stub and worker fixtures.
  - **Primary fixtures:** `_configure_celery_for_tests`, `worker_engine`, `worker_stubs`.
  - **PRs:** 1.1 (Celery stub extraction), 4.1 (remove unused worker dirs if any), 3.1 (fold into `integration` by default).
- **e2e** – End-to-end API tests.
  - **Primary areas:** `tests/api/e2e/`, Playwright suites under `services/web/tests/e2e/` (not refactored here, but coordinated).
  - **PRs:** 5.1/5.2 (if e2e tests live in large API files), 4.2 (directory audit).
- **perf / performance** – Performance-focused suites.
  - **PRs:** 3.1 (marker consolidation to `perf`), documentation updates in `docs/testing/pytest_performance.md`.
- **gpu** – GPU-required tests.
  - **PRs:** 3.1 (no structural change; ensure clearly documented as opt-in only).
- **contract** – API schema/contract tests in `tests/contracts/`.
  - **PRs:** 4.2 (keep directory but ensure discoverability), potential follow-up in a separate API contract plan.
- **redteam** – OWASP/LLM security and adversarial tests.
  - **PRs:** 3.1 (marker description only), future hardening work tracked in red-team specific docs.
- **flaky** – Tests explicitly marked as unstable.
  - **PRs:** 3.2 (remove marker after fixing or deleting tests).

### Phase 4: Directory Cleanup (Week 2)

#### PR 4.1: Remove Empty Directories

Directories to remove:

- `tests/mcp_tools/` - MCP server removed
- `tests/platform/` - Platform events removed
- `tests/case_builder/` - Never implemented

#### PR 4.2: Audit and Consolidate Small Directories

| Directory | Items | Recommendation |
|-----------|-------|----------------|
| `tests/contracts/` | 1 | Keep separate (grows with API) |
| `tests/scripts/` | 1 | Merge → `tests/unit/` |
| `tests/utils/` | 1 | Merge → `tests/unit/` |
| `tests/stubs/` | 1 | Keep (will grow with Phase 1) |

### Phase 5: Large File Splits (Week 3)

#### PR 5.1: Split `test_ai_router.py` (44KB)

Current file tests multiple AI workflows. Split into:

```text
tests/api/ai/
├── test_chat_workflow.py      # Chat completions
├── test_verse_workflow.py     # Verse analysis
├── test_sermon_workflow.py    # Sermon generation
├── test_router_common.py      # Shared router tests
└── test_router_errors.py      # Error handling
```

#### PR 5.2: Split `test_ingest.py` (37KB)

Split by ingestion source type:

```text
tests/api/ingest/
├── test_url_ingestion.py      # URL/webpage ingestion
├── test_pdf_ingestion.py      # PDF document ingestion
├── test_audio_ingestion.py    # Audio transcript ingestion
├── test_ingestion_common.py   # Shared validation tests
└── conftest.py                # Ingestion-specific fixtures
```

---

## How to Run Each Slice (using markers & paths)

These commands describe how developers should run the major slices **after** the refactor, using the consolidated markers:

- **Fast unit & API tests (default local run)**
  - Scope: everything that does **not** require Postgres/pgvector, Celery, or long-running ML.
  - Command:
    - `pytest tests -m "not integration and not pgvector and not slow and not redteam"`
- **DB-backed integration tests (SQLite/Postgres)**
  - Scope: tests that hit the real schema via `db_session` / `integration_session`.
  - Commands:
    - `pytest tests -m integration`
    - Optionally `pytest tests/api tests/ingest -m integration` for API + ingest only.
- **Postgres+pgvector tests**
  - Scope: retrieval/ingest tests that spin up the pgvector Testcontainer.
  - Command:
    - `pytest tests -m pgvector`
- **Worker/Celery tests**
  - Scope: ingestion workers and background tasks using the Celery stub.
  - Command:
    - `pytest tests/workers -m integration`
- **End-to-end API tests**
  - Scope: high-level API flows that simulate full user journeys.
  - Command:
    - `pytest tests/api -m e2e`
- **Performance and GPU tests**
  - Scope: heavy perf and GPU-only suites, run on demand or in nightly CI.
  - Commands:
    - `pytest tests -m perf`
    - `pytest tests -m gpu`
- **Red-team / security regression suite**
  - Scope: adversarial/OWASP-style tests.
  - Command:
    - `pytest tests -m redteam`

---

## Implementation Order

### Week 1

1. **PR 1.1**: Extract stubs to `tests/stubs/`
2. **PR 1.2**: Consolidate HTTP stubbing
3. **PR 2.1**: Create `tests/fixtures/database.py`

### Week 2

1. **PR 2.2**: Create `tests/fixtures/clients.py`
2. **PR 3.1**: Implement marker consolidation
3. **PR 4.1**: Remove empty directories

### Week 3

1. **PR 3.2**: Remove flaky marker (requires test fixes)
2. **PR 5.1**: Split `test_ai_router.py`
3. **PR 5.2**: Split `test_ingest.py`

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Root conftest.py lines | 1,174 | <400 |
| API conftest.py lines | 562 | <200 |
| Test markers | 11 | 7 |
| Empty test directories | 3 | 0 |
| Files >30KB | 2 | 0 |
| Average test collection time | ~15s | <8s |
| `--fast` execution time | ~45s | <30s |

---

## Risk Mitigation

### Before Each PR

1. **Run full test suite** to establish baseline
2. **Create feature branch** from main
3. **Document import changes** in PR description
4. **Run `pytest --collect-only`** to verify no collection errors

### Backwards Compatibility

- Keep marker aliases (`--schema` → `--integration`)
- Deprecation warnings for renamed fixtures
- Update `docs/testing.md` with each PR

### Rollback Plan

Each PR is atomic and reversible:

- Git revert for immediate rollback
- No cross-PR dependencies within phases
- Phase 1-2 can proceed independently of Phase 3-5

---

## Related Documents

- `docs/planning/SIMPLIFICATION_PLAN.md` - Feature removal roadmap
- `docs/planning/PROJECT_IMPROVEMENTS_ROADMAP.md` - Broader improvements
- `docs/testing.md` - Testing prerequisites
- `docs/testing/pytest_performance.md` - Performance baselines

---

## Appendix: Current Fixture Graph

```text
tests/conftest.py
├── _install_optional_dependency_stubs() [autoimport]
├── stub_example_com_requests [autouse, function]
├── downgrade_ingestion_error_logs [autouse, session]
├── _bootstrap_embedding_service_stub [autouse, function]
├── bootstrap_embedding_service_stub [function]
├── regression_factory [function]
├── application_container [function]
├── optimized_application_container [session]
├── application_container_factory [function]
├── _configure_celery_for_tests [autouse, session]
├── pgvector_db [session]
├── pgvector_container [session]
├── pgvector_database_url [session]
├── pgvector_engine [session]
├── pgvector_migrated_database_url [session]
├── shared_test_database [session]
├── ml_models [session]
├── integration_database_url [session]
├── integration_engine [session]
├── db_transaction [function]
├── integration_session [function]
├── schema_isolation [function]
├── _set_database_url_env [autouse, session]
├── manage_memory [autouse conditionally]
├── mock_sleep_session [autouse, session]
├── mock_sleep [autouse, function]
└── resource_pool [session]

tests/api/conftest.py
├── _register_*_stub() [autoimport]
├── _stub_external_integrations [autouse, session]
├── _bypass_authentication [autouse, function]
├── _disable_migrations [autouse, function]
├── _skip_heavy_startup [autouse, session]
├── _api_engine_template [session]
├── _shared_api_engine [session]
├── api_engine [function]
├── _global_test_client [session]
└── api_test_client [function]
```

---

## Next Steps

1. Review this plan with team
2. Create tracking issue for each PR
3. Begin Phase 1 implementation
4. Update this document with progress
