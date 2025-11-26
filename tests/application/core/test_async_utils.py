"""Tests for async enforcement utilities."""

from __future__ import annotations

import asyncio
import warnings

import pytest

from exegesis.application.core.async_utils import (
    BlockingCallWarning,
    async_safe,
    blocking_operation,
    is_async_context,
    run_sync,
    warn_if_async,
)


def test_is_async_context_returns_false_in_sync():
    """is_async_context returns False when not in an event loop."""
    assert is_async_context() is False


@pytest.mark.asyncio
async def test_is_async_context_returns_true_in_async():
    """is_async_context returns True inside async function."""
    assert is_async_context() is True


def test_run_sync_from_sync_raises():
    """run_sync requires an event loop to be running."""

    async def _inner():
        def blocking():
            return 42

        return await run_sync(blocking)

    result = asyncio.run(_inner())
    assert result == 42


@pytest.mark.asyncio
async def test_run_sync_executes_blocking_function():
    """run_sync offloads function to thread pool."""

    def blocking_add(a: int, b: int) -> int:
        return a + b

    result = await run_sync(blocking_add, 3, 5)
    assert result == 8


@pytest.mark.asyncio
async def test_run_sync_with_kwargs():
    """run_sync handles keyword arguments."""

    def greet(name: str, greeting: str = "Hello") -> str:
        return f"{greeting}, {name}!"

    result = await run_sync(greet, "World", greeting="Hi")
    assert result == "Hi, World!"


def test_warn_if_async_silent_in_sync():
    """warn_if_async does not warn in sync context."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        warn_if_async("test_op")
        assert len(w) == 0


@pytest.mark.asyncio
async def test_warn_if_async_warns_in_async():
    """warn_if_async emits warning in async context."""

    def trigger_warning():
        warn_if_async("blocking_op")

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        trigger_warning()
        assert len(w) == 1
        assert issubclass(w[0].category, BlockingCallWarning)
        assert "blocking_op" in str(w[0].message)


def test_blocking_operation_decorator_silent_in_sync():
    """blocking_operation decorator does not warn in sync context."""

    @blocking_operation("slow_io")
    def slow_io():
        return "done"

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = slow_io()
        assert result == "done"
        assert len(w) == 0


@pytest.mark.asyncio
async def test_blocking_operation_decorator_warns_in_async():
    """blocking_operation decorator warns in async context."""

    @blocking_operation("db_query")
    def db_query():
        return {"data": "value"}

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = db_query()
        assert result == {"data": "value"}
        assert len(w) == 1
        assert "db_query" in str(w[0].message)


def test_async_safe_runs_normally_in_sync():
    """async_safe decorated function runs normally in sync context."""

    @async_safe
    def compute(x: int) -> int:
        return x * 2

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = compute(21)
        assert result == 42
        assert len(w) == 0


@pytest.mark.asyncio
async def test_async_safe_warns_in_async():
    """async_safe decorated function warns in async context."""

    @async_safe
    def process(data: str) -> str:
        return data.upper()

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = process("hello")
        assert result == "HELLO"
        assert len(w) == 1
        assert issubclass(w[0].category, BlockingCallWarning)
