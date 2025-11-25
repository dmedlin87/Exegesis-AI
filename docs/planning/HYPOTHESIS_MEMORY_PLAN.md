# Hypothesis Memory + HUD Plan

**Created:** 2025-11-24
**Status:** Draft
**Owner:** Research / AI Platform
**Objective:** Give the model a structured, persistent "note" system (Hypotheses + Evidence) that auto-captures findings during trails and surfaces them as a HUD for future reasoning.

## Goals & Success Criteria
- Structured capture: Hypotheses stored with status/confidence/type; evidence stored as ResearchNoteEvidence with source refs and citations.
- Automatic triggers: Insight detection in trails converts high-novelty findings into Hypothesis drafts without manual ops steps.
- HUD retrieval: Relevant hypotheses injected into prompts via vector search and filters before each model call.
- Safety/quality: Deduplicate, version, and allow human promotion from draft -> active; avoid polluting HUD with low-confidence noise.
- Measurable lift: Higher answer consistency on regressions and fewer repeat lookups on topics already researched.

## Domain Mapping (Shape Analogy)
- Class/Base: Hypothesis (claim, status, confidence, claim_type, perspective_scores).
- Attributes: ResearchNoteEvidence (osis_refs, citation, provenance, confidence).
- Trigger/Note: Insight (detected via `InsightDetector.detect_from_reasoning` in `theo/infrastructure/api/app/research/ai/reasoning/insights.py`).

## Planned Workflow
1) HUD Retrieval Pipeline
- Build `HypothesisRetriever` service: embed query, search Hypotheses table/pgvector, apply filters (status != retired, min confidence), return top-k with evidence snippets.
- Add prompt block injection in the RAG pipeline (pre-LLM call) with a concise "Known Concepts" section.

2) Insight Capture in Trails
- In `TrailRecorder` (`theo/infrastructure/api/app/research/ai/trails.py`), run InsightDetector against step reasoning/output_payload when text is present.
- Map qualifying insights to HypothesisDraft objects (claim, status=draft, confidence=novelty_score, supporting_passage_ids=insight.supporting_passages, osis_refs=insight.osis_refs).
- Store pending drafts on the trail; flush on finalize to avoid partial runs polluting memory.

3) Persistence & Indexing
- Add ResearchRepository helper to upsert Hypotheses and related ResearchNoteEvidence (link to AgentTrail.id for provenance).
- Generate embeddings for hypothesis.claim on save; write to the vector index.
- Implement dedupe: hash claim text; if an existing similar hypothesis is above threshold, attach evidence instead of creating a new row.

4) Promotion & Curation
- Background task or admin action to move drafts -> active/proven; record moderator id/time.
- Optional feedback loop: allow trails to consume active hypotheses as seeds and update confidence when evidence grows.

5) Evaluation & Guardrails
- Telemetry: count drafts created, promoted, rejected; HUD hit-rate on queries.
- Quality checks: clamp HUD to top N entries; require min confidence; redact if user context forbids sharing prior research.

## Deliverables (per PR)
- PR1: `HypothesisRetriever` plus HUD prompt block wired into the RAG pipeline.
- PR2: Insight capture in TrailRecorder with pending draft buffer and persistence flush on finalize.
- PR3: Dedupe/indexing helpers and embedding storage for Hypotheses.
- PR4: Moderation/promote flow and metrics dashboards.

## Open Questions
- Where to store embeddings (pgvector vs external store) for production scale?
- Should we allow auto-promotion for very high novelty_score findings, or always require human review?
- How to expose HUD contents to users (UI chip vs hidden system note) without leaking sensitive drafts?
