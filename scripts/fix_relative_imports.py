import os
import re
import sys

mappings = {
    # Library
    r"from \.\.ingest": "from ..library.ingest",
    r"from \.\.transcripts": "from ..library.transcripts",

    # Retrieval
    r"from \.\.retriever": "from ..retrieval.retriever",
    r"from \.\.ranking": "from ..retrieval.ranking",
    r"from \.\.search": "from ..retrieval.search",
    r"from \.\.embeddings": "from ..retrieval.embeddings",

    # Research
    r"from \.\.ai": "from ..research.ai",
    r"from \.\.case_builder": "from ..research.case_builder",
    r"from \.\.notebooks": "from ..research.notebooks",
    r"from \.\.discoveries": "from ..research.discoveries",

    # Core
    r"from \.\.telemetry": "from ..core.telemetry",
    r"from \.\.tracing": "from ..core.tracing",
    r"from \.\.error_handlers": "from ..core.error_handlers",
    r"from \.\.errors": "from ..core.errors",
    r"from \.\.security": "from ..core.security",
    r"from \.\.observability": "from ..core.observability",
    r"from \.\.resilience": "from ..core.resilience",

    # 3-dot imports (grandparent)
    r"from \.\.\.ingest": "from ...library.ingest",
    r"from \.\.\.transcripts": "from ...library.transcripts",
    r"from \.\.\.retriever": "from ...retrieval.retriever",
    r"from \.\.\.ranking": "from ...retrieval.ranking",
    r"from \.\.\.search": "from ...retrieval.search",
    r"from \.\.\.embeddings": "from ...retrieval.embeddings",
    r"from \.\.\.ai": "from ...research.ai",
    r"from \.\.\.case_builder": "from ...research.case_builder",
    r"from \.\.\.notebooks": "from ...research.notebooks",
    r"from \.\.\.discoveries": "from ...research.discoveries",
    r"from \.\.\.telemetry": "from ...core.telemetry",
    r"from \.\.\.tracing": "from ...core.tracing",
    r"from \.\.\.error_handlers": "from ...core.error_handlers",
    r"from \.\.\.errors": "from ...core.errors",
    r"from \.\.\.security": "from ...core.security",
    r"from \.\.\.observability": "from ...core.observability",
    r"from \.\.\.resilience": "from ...core.resilience",
}

def fix_imports(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        return

    original = content
    for pattern, replacement in mappings.items():
        content = re.sub(pattern, replacement, content)

    if content != original:
        print(f"Fixed relative imports in {filepath}", flush=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

def main():
    target_dir = "theo"
    print(f"Scanning {target_dir} recursively", flush=True)
    for root, dirs, files in os.walk(target_dir):
        for file in files:
            if file.endswith(".py"):
                fix_imports(os.path.join(root, file))

if __name__ == "__main__":
    main()
