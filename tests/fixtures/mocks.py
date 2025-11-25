"""Session-wide mocks for expensive external integrations.

This module provides session-scoped patches for expensive external dependencies
to avoid repeated mock setup overhead. The patches are automatically applied
via auto-use fixtures.

Fixtures
--------
optimize_mocks : session, autouse
    Patches httpx.AsyncClient and Celery.__init__ for deterministic behavior.
    Returns a dict containing mock references for explicit assertions.

_reset_session_mocks : function, autouse
    Resets call history on session-scoped mocks between tests to prevent
    cross-test assertion pollution.
"""

from __future__ import annotations

from contextlib import ExitStack
from typing import Any, Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(scope="session", autouse=True)
def optimize_mocks() -> Generator[dict[str, Any], None, None]:
    """Provide deterministic mocks for heavy external dependencies.

    Yields a dict with mock references so tests can assert on them:
    - "httpx_async_client": The patched AsyncClient instance
    - "httpx_response": The mock response returned by get()
    """

    mocks: dict[str, Any] = {}

    with ExitStack() as stack:
        try:
            async_client_patch = stack.enter_context(patch("httpx.AsyncClient"))
        except ModuleNotFoundError:
            async_client_patch = None
        else:
            async_client = AsyncMock()
            context_client = AsyncMock()
            response_mock = AsyncMock()
            response_mock.status_code = 200
            context_client.get.return_value = response_mock
            async_client.__aenter__.return_value = context_client
            async_client.__aexit__.return_value = False
            async_client.get.return_value = response_mock
            async_client_patch.return_value = async_client
            mocks["httpx_async_client"] = async_client
            mocks["httpx_context_client"] = context_client
            mocks["httpx_response"] = response_mock

        try:
            from celery import Celery as CeleryClass
        except ModuleNotFoundError:
            celery_init_patch = None
        else:
            original_init = CeleryClass.__init__

            def _patched_init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                original_init(self, *args, **kwargs)
                conf = getattr(self, "conf", None)
                if conf is not None:
                    conf.task_always_eager = True
                    conf.task_ignore_result = True
                    if hasattr(conf, "task_store_eager_result"):
                        conf.task_store_eager_result = False

            celery_init_patch = stack.enter_context(
                patch.object(CeleryClass, "__init__", _patched_init)
            )

        yield mocks


@pytest.fixture(autouse=True)
def _reset_session_mocks(optimize_mocks: dict[str, Any]) -> Generator[None, None, None]:
    """Reset call history on session-scoped mocks after each test.

    This prevents cross-test assertion pollution where a mock's call_count
    or call_args from a previous test could affect assertions in subsequent tests.
    """

    yield

    # Reset httpx mocks if they exist
    if "httpx_async_client" in optimize_mocks:
        optimize_mocks["httpx_async_client"].reset_mock()
    if "httpx_context_client" in optimize_mocks:
        optimize_mocks["httpx_context_client"].reset_mock()
    if "httpx_response" in optimize_mocks:
        optimize_mocks["httpx_response"].reset_mock()
