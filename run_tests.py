#!/usr/bin/env python3
"""Entry point for running the pytest suite with optional plugins.

.. deprecated:: 2025.11
    This module is deprecated. Use direct ``pytest`` invocation instead.
    All conditional plugin configuration has been moved to ``tests/conftest.py``
    and ``pyproject.toml``.

    Simply run::

        pytest [options]

    The following features are now handled automatically:
    - pytest-timeout: Configured in pytest_configure (60s default)
    - pytest-xdist: Registered dynamically when available
    - pytest-cov: Use --cov=theo directly

    This script will be removed in a future release.
"""

from __future__ import annotations

import importlib
import importlib.util
import subprocess
import sys
import warnings
from typing import List

# Emit deprecation warning on import
warnings.warn(
    "run_tests.py is deprecated. Use 'pytest' directly instead. "
    "See module docstring for migration details.",
    DeprecationWarning,
    stacklevel=2,
)


def _has_plugin(module_name: str) -> bool:
    """Return True if the given module can be imported."""

    spec = importlib.util.find_spec(module_name)
    if spec is None:
        return False

    try:
        importlib.import_module(module_name)
    except ImportError:
        return False

    return True


def _build_base_args() -> List[str]:
    """Construct the base pytest command line."""

    return [
        sys.executable,
        "-m",
        "pytest",
        "-ra",
        "--strict-markers",
        "--durations=50",
        "--durations-min=0.05",
    ]


def _extend_with_optional_plugins(args: List[str]) -> None:
    """Add arguments that depend on optional plugins."""

    if _has_plugin("pytest_timeout"):
        args.append("--timeout=60")
    else:
        print("pytest-timeout not available; running without global timeout")

    if _has_plugin("xdist"):
        print("Running tests with pytest-xdist parallel execution")
        args.extend(["-n=auto", "--dist=worksteal"])
    else:
        print("Running tests sequentially (pytest-xdist not available)")

    if _has_plugin("pytest_cov"):
        args.extend(["--cov=theo", "--cov-report=term-missing"])


def main() -> int:
    """Execute the configured pytest command."""

    args = _build_base_args()
    _extend_with_optional_plugins(args)

    try:
        completed = subprocess.run(args, check=False)
    except FileNotFoundError:  # pragma: no cover - defensive guard
        print("pytest not found. Please ensure it is installed.")
        return 1

    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
