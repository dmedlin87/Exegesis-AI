# Remaining Steps to Fix RAG Module Imports

## 1. Current Status

-   **Fixed Imports:**
    -   `theo/infrastructure/api/app/research/ai/trails.py`
    -   `theo/infrastructure/api/app/research/ai/rag/guardrail_helpers.py`
    -   `theo/infrastructure/api/app/research/ai/rag/guardrails.py`
    -   `theo/infrastructure/api/app/research/ai/rag/prompts.py`
    -   `theo/infrastructure/api/app/research/ai/rag/refusals.py`
    -   `theo/infrastructure/api/app/research/ai/rag/verse.py`
    -   `theo/infrastructure/api/app/research/ai/rag/chat.py` (partially fixed, switched to absolute import)
-   **Pending Issues:**
    -   `theo.infrastructure.api.app.research.ai.rag.reasoning` fails with `No module named 'theo.infrastructure.api.app.research.models'`.
    -   `theo.infrastructure.api.app.research.ai.rag.chat` still failing with the same error despite the fix (likely due to transitive imports or another bad import line).
    -   `theo.infrastructure.api.app.research.ai.rag.collaboration` fails with the same error.
    -   `theo.infrastructure.api.app.research.ai.rag.verse` fails with the same error.
    -   `theo.infrastructure.api.app.research.ai.rag.workflow` fails because of the above issues (triggering the fallback error).

## 2. Next Actions

1.  **Fix `reasoning.py`:**
    -   Open `theo/infrastructure/api/app/research/ai/rag/reasoning.py`.
    -   Identify incorrect relative imports (likely `from ...models` or similar).
    -   Change them to absolute imports: `from theo.infrastructure.api.app.models...` or correct the relative path.
2.  **Fix `collaboration.py`:**
    -   Open `theo/infrastructure/api/app/research/ai/rag/collaboration.py`.
    -   Fix incorrect relative imports.
3.  **Re-verify `chat.py` and `verse.py`:**
    -   Ensure _all_ incorrect relative imports are resolved. The persistent error suggests there might be more than one, or a shared dependency is still broken.
4.  **Run Debug Script:**
    -   Execute `python debug_rag_import.py` to verify that `reasoning`, `chat`, `collaboration`, and `verse` can be imported successfully.
5.  **Run Tests:**
    -   Once the debug script shows "OK" for all modules, run `python -m pytest tests/api/retriever/test_ranking.py` to confirm the original issue is resolved.

## 3. Broader Verification

-   Run the full test suite `tests/api/` to ensure no regressions.
-   Check for any other `from ...models` patterns in `theo/infrastructure/api/app/research/ai/rag/` that might have been missed.
