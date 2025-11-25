# Remaining Steps to Fix RAG Module Imports

## 1. Current Status

-   **Fixed Imports:**
    -   `theo/infrastructure/api/app/research/ai/trails.py`
    -   `theo/infrastructure/api/app/research/ai/rag/guardrail_helpers.py`
    -   `theo/infrastructure/api/app/research/ai/rag/guardrails.py`
    -   `theo/infrastructure/api/app/research/ai/rag/prompts.py`
    -   `theo/infrastructure/api/app/research/ai/rag/refusals.py`
    -   `theo/infrastructure/api/app/research/ai/rag/chat.py` (partially fixed, switched to absolute import)
    -   `theo/infrastructure/api/app/research/ai/rag/reasoning.py` (imports rewritten to absolute paths under `theo.infrastructure.api.app`)
    -   `theo/infrastructure/api/app/research/ai/rag/collaboration.py` (imports aligned with the canonical module namespace)
    -   `theo/infrastructure/api/app/research/ai/rag/verse.py` (resolved incorrect relative imports)

## 2. Next Actions

1.  **Keep sanity checks green:**
    -   The latest run of `python debug_rag_import.py` already shows successful imports for `reasoning`, `chat`, `collaboration`, and `verse` after the absolute-import fixes.
    -   `python -m pytest tests/api/retriever/test_ranking.py` is also passing per the validation log; re-run these only if new changes touch the RAG module tree or its dependencies.
2.  **Broader verification:**
    -   Proceed to wider coverage to catch any remaining regressions beyond the targeted import fixes (see Section 4).

## 3. Validation Log (2025-02-19)

-   Installed missing runtime dependencies to satisfy the RAG imports and API bootstrap during testing: `sqlalchemy`, `pydantic`, `pydantic-settings`, `pythonbible`, `httpx`, `cachetools`, `opentelemetry-api`, `pypdf`, `fastapi`, `PyJWT`, `pyyaml`, `joblib`, `numpy`, `networkx`, and `python-multipart`.
-   `python debug_rag_import.py` now reports successful imports for `reasoning`, `chat`, `collaboration`, and `verse`, along with the other RAG modules.
-   `python -m pytest tests/api/retriever/test_ranking.py` passes (1 test, 1 warning about `celery.contrib.pytest` already imported for assert rewriting).

## 4. Broader Verification

-   Run the full test suite `tests/api/` to ensure no regressions.
-   Check for any other `from ...models` patterns in `theo/infrastructure/api/app/research/ai/rag/` that might have been missed.
