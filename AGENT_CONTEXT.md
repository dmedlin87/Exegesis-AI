> **DOCUMENTATION PROTOCOL**
> Before creating ANY text file, you MUST read `docs/00_DOCUMENTATION_STRATEGY.md` to determine the correct subdirectory. Usage of the root `docs/` folder for new files is strictly PROHIBITED.

# Agent Context & Current Architecture

[⬅️ Back to the README](README.md)

This document distills the essential architecture, conventions, and active surfaces compiled from the legacy agent handoff packages, [`IMPLEMENTATION_CONTEXT.md`](IMPLEMENTATION_CONTEXT.md), and the current repository layout. Treat it as the living context file that complements the product overview in the README.

---

## Platform Snapshot

- **Product mission** – Exegesis AI delivers deterministic, verse-anchored theological research workflows with hybrid retrieval, agent assistance, and UI automation. (See the "Why Exegesis AI" and "Core Capabilities" sections in the [README](README.md).)
- **Primary stacks** – FastAPI workers and background jobs (`theo/infrastructure/api`), Next.js app router frontend (`theo/services/web`), PostgreSQL with `pgvector`, and MCP tooling for automations.
- **Operational guardrails** – Scripts under `scripts/` orchestrate dev loops, while `task` targets and `pytest` suites enforce regression safety. Refer to [`CONTRIBUTING.md`](CONTRIBUTING.md) for expectations.

## Architecture Highlights

- **Hexagonal layering** – Domain logic in `theo/domain` stays pure and framework-free; application facades in `theo/application` orchestrate persistence; adapters integrate external systems; services expose APIs and UI. [`IMPLEMENTATION_CONTEXT.md`](IMPLEMENTATION_CONTEXT.md) contains diagrams and code templates for ports/adapters.
- **Discovery engines** – Engines share the `dataclass` + `.detect()` contract and are registered in `theo/infrastructure/api/app/discoveries/service.py`. Follow the sample patterns in [`IMPLEMENTATION_CONTEXT.md`](IMPLEMENTATION_CONTEXT.md#architecture-patterns) when adding new discovery types.
- **Agent & prompting guardrails** – Safety patterns and operational limits live in [`docs/AGENT_AND_PROMPTING_GUIDE.md`](docs/AGENT_AND_PROMPTING_GUIDE.md) and [`docs/AGENT_CONFINEMENT.md`](docs/AGENT_CONFINEMENT.md); align new reasoning flows with those constraints.

## Development Workflow

1. **Bootstrap tooling** with the launcher in [`START_HERE.md`](START_HERE.md) or manually via the Quick Start commands in the [README](README.md#quick-start).
2. **Run targeted tests** (`task test:fast`, `pytest -m "not slow"`) before iterating on discovery engines or API changes; see [`docs/testing/TEST_MAP.md`](docs/testing/TEST_MAP.md) for full coverage expectations.
3. **Observe type standards** in both Python (`mypy.ini`, `typing-standards.md`) and TypeScript (`theo/services/web` uses strict TypeScript and CSS modules).
4. **Document changes** by updating [`CHANGELOG.md`](CHANGELOG.md) and the archive directories when you complete a handoff or retire docs.

## Test Suite & Fixtures Overview

- **Markers & suites** – Pytest markers such as `integration`, `slow`, `pgvector`, `schema`, `no_auth_override`, `reset_state`, and `redteam` are declared under `[tool.pytest.ini_options]` in `pyproject.toml` and wired through `_SUITE_CONFIG` in `tests/conftest.py`.
- **Global test hooks** – `tests/conftest.py` registers plugins (e.g. `pytest-timeout`, `pytest-randomly`, `celery.contrib.pytest`), auto-adds suite fixtures during collection, installs a deterministic embedding stub, and exposes `reset_global_state` to clear engines, settings caches, and telemetry between tests.
- **API tests** – `tests/api/conftest.py` provides `api_test_client`, which uses a per-test SQLite copy of a migrated template database and overrides `get_session`. Authentication is bypassed by default; apply `@pytest.mark.no_auth_override` to exercise real auth flows.
- **Postgres/pgvector integration tests** – `tests/fixtures/pgvector.py` and `tests/conftest.py::pgvector_db` provision a Postgres+pgvector Testcontainer, prepare a template schema, and clone databases for `integration_session` with nested transactions and savepoint-based rollback.
- **Worker & ingestion tests** – `tests/workers/conftest.py` configures Celery for eager, in-process execution and stubs ingestion/search/citation dependencies; `tests/ingest/conftest.py` clones pgvector databases for pipeline tests and provides `pipeline_session_factory` with transaction rollback, plus performance stubs for `pythonbible`.
- **Domain & application tests** – `tests/factories/application.py::isolated_application_container` and `tests/conftest.py::application_container` yield fresh `ApplicationContainer` instances with overridable factories; `tests/fixtures/research.py` supplies in-memory SQLite sessions and persisted `ResearchNote` fixtures for domain-level tests.

## Current Priorities

- **Stabilize contradiction seed migrations, harden ingest error handling, and repair router inflight deduplication.** The concrete tasks and references are tracked in [`docs/planning/SIMPLIFICATION_PLAN.md`](docs/planning/SIMPLIFICATION_PLAN.md).
- **Maintain documentation hygiene.** Any new handoff or summary should land under `docs/archive/handoffs/` while the canonical entry points stay in the repository root. Update [`docs/document_inventory.md`](docs/document_inventory.md) after every reorganization.

## Where to Dive Deeper

- [`docs/INDEX.md`](docs/INDEX.md) - Global navigation by persona and domain area.
- [`docs/architecture.md`](docs/architecture.md) - Current system architecture overview and diagrams.
- [`docs/API.md`](docs/API.md) - REST and agent surface contracts.
- [`docs/document_inventory.md`](docs/document_inventory.md) - Manifest of active docs and archive policies.
- [`docs/Repo-Health.md`](docs/Repo-Health.md) - Operational dashboards, maintenance checklists, and runbooks.

---

Return to the [README](README.md) whenever you need the canonical elevator pitch or onboarding map. This context file focuses on the technical surface area so you can move from orientation to execution without re-reading every archived handoff.
