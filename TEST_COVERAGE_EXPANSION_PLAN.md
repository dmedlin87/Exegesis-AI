# Test Coverage Expansion Plan

## Executive Summary
**Current Overall Coverage:** ~27%
**Target Baseline:** 80%

The current test coverage is insufficient for a production-grade system, particularly in the core business logic (`theo.domain`) and infrastructure layers (`theo.infrastructure`). The current documentation regarding coverage is unreliable; this document establishes the ground truth and the roadmap for remediation.

## Current Status Analysis

Based on the latest system audit (Nov 2025):

| Module | Coverage | Risk Level | Analysis |
|--------|----------|------------|----------|
| **theo.domain** | 29.67% | **CRITICAL** | Contains the core business rules (e.g., `biblical_texts.py`, discoveries). Low coverage here means business logic bugs go undetected. |
| **theo.services** | 14.53% | **CRITICAL** | The orchestration layer is largely untested. This suggests a lack of integration tests for service flows. |
| **theo.infrastructure** | 20.72% | **HIGH** | Adapters for databases and external services are brittle. 20% suggests successful paths might be tested, but error handling and edge cases are ignored. |
| **fastapi** | 21.00% | **HIGH** | API Routes are under-tested. This implies the public interface contract is not guaranteed. |
| **celery** | 56.60% | MEDIUM | Async task coverage is better but still leaves 40% of background processing logic exposed. |

## Expansion Plan

We will execute a 3-phase expansion strategy to raise the baseline efficiently, prioritizing system stability and correctness.

### Phase 1: Core Domain Logic (Target: 90%)
**Goal:** Guarantee business rule correctness. These tests are fast, cheap, and high-value.

*   **Focus Areas:**
    *   `theo.domain.biblical_texts`: Complete unit test suite for `BiblicalVerse`, `TheologicalTermTracker`, and parsing logic.
    *   `theo.domain.discoveries`: rigorous testing of discovery algorithms.
    *   `theo.domain.research`: validation of research data models and logic.
*   **Action Items:**
    1.  Audit `tests/domain` for missing test files corresponding to domain modules.
    2.  Implement comprehensive property-based testing (using `hypothesis`) for parsing and data transformation logic.
    3.  Mock nothing in this layer; domain objects should be pure.

### Phase 2: Infrastructure Reliability (Target: 80%)
**Goal:** Ensure robust integration with external systems and resilience to failure.

*   **Focus Areas:**
    *   `theo.infrastructure.api`: This likely contains the concrete implementations of repositories and adapters.
    *   `theo.infrastructure.data`: Data access layers.
*   **Action Items:**
    1.  Implement "Contract Tests" for repositories to ensure in-memory fakes and real database implementations behave identically.
    2.  Test error handling paths in adapters (e.g., what happens when the DB is down, or an external API 500s).
    3.  Verify retry logic in `celery` tasks.

### Phase 3: Service & API Integration (Target: 60%+)
**Goal:** Verify system cohesion and happy-path user flows.

*   **Focus Areas:**
    *   `theo.services.api`: The python service layer.
    *   `fastapi`: Route handlers.
*   **Action Items:**
    1.  Add integration tests for critical user journeys (e.g., "User searches for text -> Results returned -> Discovery logged").
    2.  Use `TestClient` for FastAPI route testing, ensuring all status codes (200, 400, 401, 403, 404, 500) are covered for every endpoint.
    3.  **Do not** test business logic in the controller; ensure the controller delegates correctly to the Service/Domain layer.

## Progress Report (Nov 23, 2025)

We have successfully executed the initial steps of Phase 1 and Phase 2.

### Completed Actions
1.  **Domain Logic (`theo.domain.biblical_texts`)**:
    *   Implemented `tests/domain/test_theological_term_tracker_detailed.py`.
    *   **Impact**: Full branch coverage for `TheologicalTermTracker.find_elohim_singular_verbs` logic, covering singular/plural detection, verb matching, and edge cases (missing fields, case sensitivity).

2.  **Domain Logic (`theo.domain.discoveries.trend_engine`)**:
    *   Implemented `tests/domain/discoveries/test_trend_engine_detailed.py`.
    *   **Impact**: Covered complex edge cases in `TrendDiscoveryEngine`:
        *   Date formatting across year/month boundaries.
        *   Robust float coercion for dirty data.
        *   Distribution extraction from varied metadata formats.
        *   Filtering of weak/insufficient signals.

3.  **Infrastructure Reliability (`theo.infrastructure.api.app.adapters.telemetry`)**:
    *   Implemented `tests/api/test_telemetry_errors.py`.
    *   **Impact**: Verified resilience of the `ApiTelemetryProvider`. Confirmed that span creation failures, user code exceptions, and metric recording errors are logged gracefully without crashing the application.

### Updated Metrics (Estimated)
*   **theo.domain**: Expected increase from ~29% to >40% due to deep coverage of core engines.
*   **theo.infrastructure**: Resilience patterns now verified; actual line coverage metric may remain stable due to `pragma: no cover` on defensive blocks, but *effective* reliability is significantly higher.

## Immediate Next Steps (Sprint 1)

1.  **Domain Lockdown**: Raise `theo.domain` coverage to >50%.
    *   Task: Write unit tests for `TheologicalTermTracker` in `theo/domain/biblical_texts.py`. (DONE)
    *   **Next Task**: Audit `theo.domain.discoveries.gap_engine` for similar edge cases.
2.  **Infrastructure Safety**: Identify the top 3 most used adapters in `theo.infrastructure` and add error-case testing.
    *   Telemetry Adapter (DONE).
    *   **Next Task**: `theo.infrastructure.api.app.adapters.resilience`.
3.  **Coverage CI**: Integrate a strict coverage check in the CI pipeline that fails if coverage drops on a PR (even if absolute value is low, delta must be non-negative).

## Rules of Engagement
*   **No "Assertion-free" tests**: Every test must verify a specific behavior/state, not just run the code.
*   **Prefer pure unit tests** for Domain.
*   **Prefer integration tests** (with Dockerized DB) for Infrastructure/Repositories.
