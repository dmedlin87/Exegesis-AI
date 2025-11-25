import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Redirect the `ranking` package namespace to the project's standalone `ranking/` module.
__path__[:] = [str((ROOT / "ranking").resolve())]
