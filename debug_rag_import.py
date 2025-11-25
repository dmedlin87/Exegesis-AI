import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.getcwd())

try:
    import exegesis.infrastructure.api.app.research.ai.rag
    print("Import successful")
except ImportError as e:
    print(f"Import failed: {e}")
except Exception as e:
    print(f"An error occurred: {e}")

# Also try to import the specific modules inside rag/__init__.py to see which one fails
print("\nAttempting individual imports:")
modules = [
    "theo.infrastructure.api.app.research.ai.trails",
    "theo.infrastructure.api.app.research.ai.rag.reasoning",
    "theo.infrastructure.api.app.research.ai.rag.chat",
    "theo.infrastructure.api.app.research.ai.rag.collaboration",
    "theo.infrastructure.api.app.research.ai.rag.corpus",
    "theo.infrastructure.api.app.research.ai.rag.deliverables",
    "theo.infrastructure.api.app.research.ai.rag.guardrail_helpers",
    "theo.infrastructure.api.app.research.ai.rag.guardrails",
    "theo.infrastructure.api.app.research.ai.rag.refusals",
    "theo.infrastructure.api.app.research.ai.rag.retrieval",
    "theo.infrastructure.api.app.research.ai.rag.verse",
    "theo.infrastructure.api.app.research.ai.rag.workflow",
]

import importlib
for module in modules:
    try:
        importlib.import_module(module)
        print(f"  {module}: OK")
    except Exception as e:
        print(f"  {module}: FAILED - {e}")
