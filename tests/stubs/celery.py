from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
import types
from pathlib import Path
from typing import Any


def install_celery_stubs(project_root: Path) -> None:
    """Ensure Celery and celery.contrib.pytest are importable for tests.

    This mirrors the inline stub logic previously defined in ``tests/conftest.py``
    so that Celery-related shims live in a dedicated, reusable module.
    """

    # 1. Ensure Celery is available (either real or stubbed)
    try:  # pragma: no cover - exercised indirectly via imports
        import celery  # type: ignore[import]  # noqa: F401
    except ImportError:  # pragma: no cover - lightweight environments
        celery = types.ModuleType("celery")
        celery.__path__ = []  # Mark as package

        class CeleryStub:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                self.conf = types.SimpleNamespace(
                    task_always_eager=True,
                    task_eager_propagates=True,
                    broker_url="memory://",
                    result_backend="memory://",
                    beat_schedule={},
                )

            def task(self, *args: Any, **kwargs: Any):  # type: ignore[override]
                def decorator(func):
                    func.delay = lambda *a, **k: func(*a, **k)  # type: ignore[attr-defined]
                    return func

                return decorator

        celery.Celery = CeleryStub  # type: ignore[attr-defined]

        # Stub exceptions
        celery.exceptions = types.ModuleType("celery.exceptions")

        class Retry(Exception):
            pass

        celery.exceptions.Retry = Retry  # type: ignore[attr-defined]

        # Stub schedules
        celery.schedules = types.ModuleType("celery.schedules")
        celery.schedules.crontab = lambda **k: k

        # Stub utils.log
        celery.utils = types.ModuleType("celery.utils")
        celery.utils.log = types.ModuleType("celery.utils.log")
        celery.utils.log.get_task_logger = lambda name: logging.getLogger(name)

        sys.modules["celery"] = celery
        sys.modules["celery.exceptions"] = celery.exceptions
        sys.modules["celery.schedules"] = celery.schedules
        sys.modules["celery.utils"] = celery.utils
        sys.modules["celery.utils.log"] = celery.utils.log

    # 2. Ensure celery.contrib.pytest is available
    try:  # pragma: no cover - exercised via pytest plugin loading
        import celery.contrib.pytest  # type: ignore[import]  # noqa: F401
    except ImportError:  # pragma: no cover - fallback to local plugin copy
        local_plugin = project_root / "celery" / "contrib" / "pytest.py"
        if local_plugin.exists():
            spec = importlib.util.spec_from_file_location(
                "celery.contrib.pytest", str(local_plugin)
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules["celery.contrib.pytest"] = module
                spec.loader.exec_module(module)
