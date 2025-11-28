# ADR 0002: Refine into Modular Monolith with Bounded Contexts

- **Status**: Proposed
- **Date**: 2025-11-23
- **Context**: Review feedback suggests refining Exegesis AI into a "modular monolith" with sharper bounded contexts and runtime separation for heavy work, rather than splitting into microservices.

## Context

The current architecture has good layering (`domain` -> `application` -> `infrastructure`), but the `application` and `infrastructure/api` layers are becoming cluttered. There is a mix of concerns (ingestion, retrieval, research) co-located without clear boundaries. We want to avoid the operational complexity of microservices while achieving better modularity and scalability for heavy workloads.

## Decision

We will adopt a **Modular Monolith** architecture with the following characteristics:

### 1. Runtime Topology

- **API Gateway**: `theo/infrastructure/api/app/main.py` (FastAPI) remains the single HTTP edge. It handles coordination and lightweight read/write operations.
- **Worker**: Celery/RQ process (reusing code under `celery/` and `theo/application/services`) handles heavy lifting: ingestion, embeddings, enrichment, long-running research jobs. Triggered by the API via queue/outbox.
- **Web**: Next.js (future) consumes the same API.
- **Data Plane**: Postgres + pgvector (system of record), Object Storage (raw uploads), Redis (optional search cache).

### 2. Bounded Contexts

We will organize code into the following Bounded Contexts. These will be reflected in the directory structure under `theo/application` and `theo/infrastructure/api/app`.

| Context | Responsibility | Key Components |
| :--- | :--- | :--- |
| **Canonical Texts** (`canon`) | OSIS normalization, verse metadata, morphology. | `theo/domain/biblical_texts.py`, `docs/BIBLE_TEXT_SCHEMA.md` |
| **Library & Ingestion** (`library`) | Sources, parsing, frontmatter, uploads, document lifecycle. | `ingest`, `transcripts`, `creators` |
| **Retrieval & Ranking** (`retrieval`) | Embeddings, hybrid search, query planning, pgvector indexes. | `retriever`, `ranking`, `embeddings` |
| **Research & Sessions** (`research`) | Notebooks, cases, conclusions, prompts, traces. | `research`, `case_builder`, `notebooks` |
| **Observability & Auth** (`core`) | Telemetry, error handlers, auth config, rate limits. | `telemetry`, `error_handlers`, `auth` |

### 3. Contracts & Interaction

- **Cross-Context Contracts**: DTOs and Repository interfaces (`theo/application/dtos`, `.../repositories`) are the only allowed cross-context dependencies.
- **No Shared ORM Models**: ORM models are private to their context's infrastructure layer.
- **Async Handoff**: Use an internal event/outbox pattern for API -> Worker handoff (e.g., ingest request, embedding rebuild).

### 4. Migration Steps

1. **Phase 1: Cleanup**: Execute `docs/planning/SIMPLIFICATION_PLAN.md` (remove `mcp_server`, simplify `checkpoints`).
2. **Phase 2: Structure**: Move existing folders into context-specific subdirectories under `theo/application` and `theo/infrastructure/api/app`.
   - `theo/infrastructure/api/app/ingest` -> `theo/infrastructure/api/app/library/ingest`
   - `theo/infrastructure/api/app/retriever` -> `theo/infrastructure/api/app/retrieval/search`
   - etc.
3. **Phase 3: Extract Core**: Ensure `theo/domain` + `theo/application` form a "core" package that is framework-agnostic.
4. **Phase 4: Async Enforcement**: Move slow paths (ingestion, embeddings) to background workers if not already there.

## Consequences

- **Positive**: clearer boundaries, easier to navigate, easier to scale heavy workers independently, prepared for potential future extraction of services if strictly necessary.
- **Negative**: strictly enforcing boundaries requires discipline (and eventually linter rules); moving files breaks git history for those files (mitigated by doing it in one go).
