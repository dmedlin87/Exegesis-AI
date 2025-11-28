# Deprecated Feature Manifest (2025-11 Cleanup)

This manifest links items flagged as deprecated in the `docs/archive/` tree to their remaining code paths so we can tell whether the functionality still runs or has been intentionally retired.

## 1. `--use-pgvector` (legacy CLI flag / `PYTEST_USE_PGVECTOR`)
* **Documented retirement:** `docs/archive/cleanup_2025_11/testing.md:70-80` now prefers `--pgvector`, calls out `--use-pgvector` as deprecated, and notes the slow-path fixture invocations that rely on the `pgvector` suite. `docs/archive/2025-10-26_core/TEST_DATABASE_SCHEMA_ISSUE.md:32-57` echoes the same opt-in pattern.
* **Code state:** `tests/conftest.py` still defines the `--pgvector` suite plus `pgvector_<component>` fixtures (lines ~360‑430, 1118‑1180) that bootstrap a seeded Postgres/Testcontainer instance. Compatibility with legacy runs is preserved in `exegesis/infrastructure/api/tests/conftest.py:50-72`, where `_use_pgvector_backend` falls back to `os.environ["PYTEST_USE_PGVECTOR"]` when the modern CLI option is absent.
* **Implication:** The flag path remains active for compatibility (env-guarded), but new workflows should use `--pgvector`/`--schema` and decorate tests with `@pytest.mark.pgvector`.

## 2. `@wait_container_is_ready` decorator
* **Documented retirement:** `docs/archive/cleanup_2025_11/testing.md:70-80` explains that newer `testcontainers` releases rely on structured wait strategies instead of the deprecated decorator.
* **Code state:** `tests/fixtures/pgvector.py:15-29` imports `LogMessageWaitStrategy`, and the provisioner (`tests/fixtures/pgvector.py:176-196`) attaches that wait strategy when the decorator used to run. No call site retains the decorator; the comment there explicitly notes the removal.
* **Implication:** Container readiness relies on logs now, making the old decorator a dead code path.

## 3. `schemathesis.experimental` module
* **Documented retirement:** `docs/archive/fixes/BUG_SWEEP.md:16-22` lists failing contract tests that import `schemathesis.experimental`, which disappeared in Schemathesis 4.
* **Code state:** `tests/contracts/test_schemathesis.py:15-26` attempts to import `experimental` inside a `try/except`, defaulting to `None` when the module is unavailable.
* **Implication:** Tests keep the import guard purely for backwards compatibility; the experimental module is no longer part of the installed dependency graph.

## 4. Legacy `theo` namespace imports
* **Documented retirement:** `docs/archive/fixes/BUG_SWEEP.md:6-32` still references `theo.services.api.app.ai.rag`, `theo.services.cli`, and other `theo.*` entry points that triggered circular imports in the old tree.
* **Code state:** `tests/api/core/test_comprehensive_core.py:24-60` programmatically builds `sys.modules` entries so that importing `theo.infrastructure.api.app.core` aliases to `exegesis.infrastructure.api.app.core.*`, which is where the live implementations now live. The shim package (`exegesis/infrastructure/api/app/core/__init__.py`) documents this aliasing approach as a deprecation path.
* **Implication:** The `theo` bundle no longer exists; the only surviving references are compatibility alias shims that re-export `exegesis` symbols for legacy callers.
