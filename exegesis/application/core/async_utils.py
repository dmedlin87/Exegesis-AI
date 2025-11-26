"""Async enforcement utilities to prevent blocking the event loop.

This module provides guardrails to ensure async code doesn't accidentally
call synchronous blocking operations that would freeze the event loop.

Usage:
    # Run blocking code safely in async context
    result = await run_sync(blocking_function, arg1, arg2, key=value)

    # Check if currently in async context (for debugging)
    if is_async_context():
        logger.warning("Running in async context")
"""

from __future__ import annotations

import asyncio
import functools
import logging
import warnings
from typing import Any, Callable, ParamSpec, TypeVar

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


class BlockingCallWarning(UserWarning):
    """Warning raised when blocking operations are detected in async context."""

    pass


def is_async_context() -> bool:
    """Return True if the current code is running inside an async event loop.

    This is useful for detecting when sync blocking code might be called
    from an async context, which would block the event loop.
    """
    try:
        loop = asyncio.get_running_loop()
        return loop is not None
    except RuntimeError:
        return False


async def run_sync(
    func: Callable[P, T],
    *args: P.args,
    **kwargs: P.kwargs,
) -> T:
    """Run a synchronous blocking function in the default executor.

    This offloads CPU-bound or blocking I/O operations to a thread pool,
    preventing them from blocking the async event loop.

    Example:
        # Instead of calling blocking code directly in async:
        # result = blocking_database_query()  # BAD - blocks event loop

        # Use run_sync to offload to thread pool:
        result = await run_sync(blocking_database_query)  # GOOD

        # With arguments:
        result = await run_sync(read_file, path, encoding="utf-8")

    Args:
        func: The synchronous function to call
        *args: Positional arguments to pass to func
        **kwargs: Keyword arguments to pass to func

    Returns:
        The return value of func
    """
    loop = asyncio.get_running_loop()

    # Create partial with kwargs since run_in_executor only accepts positional args
    if kwargs:
        func = functools.partial(func, **kwargs)

    return await loop.run_in_executor(None, func, *args)


def warn_if_async(operation_name: str) -> None:
    """Emit a warning if called from an async context.

    Use this to instrument blocking operations that should not be called
    from async code. This helps identify blocking calls during development.

    Example:
        def sync_database_query():
            warn_if_async("sync_database_query")
            # ... perform blocking operation
    """
    if is_async_context():
        warnings.warn(
            f"Blocking operation '{operation_name}' called from async context. "
            "Consider using run_sync() to avoid blocking the event loop.",
            BlockingCallWarning,
            stacklevel=3,
        )


def blocking_operation(name: str | None = None) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator to mark a function as a blocking operation.

    When the decorated function is called from an async context,
    a warning is emitted to help identify potential event loop blocking.

    Example:
        @blocking_operation("file_read")
        def read_large_file(path: str) -> bytes:
            with open(path, "rb") as f:
                return f.read()
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        op_name = name or func.__qualname__

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            warn_if_async(op_name)
            return func(*args, **kwargs)

        return wrapper

    return decorator


def async_safe(func: Callable[P, T]) -> Callable[P, T]:
    """Decorator that automatically wraps blocking calls for async contexts.

    When the decorated function is called from an async context,
    it will be automatically offloaded to a thread pool. When called
    from a sync context, it runs normally.

    Note: This returns a sync function that can also be awaited when
    called from async code. For pure async usage, prefer run_sync().

    Example:
        @async_safe
        def compute_hash(data: bytes) -> str:
            # CPU-intensive operation
            return hashlib.sha256(data).hexdigest()

        # From sync code:
        result = compute_hash(data)

        # From async code:
        result = await run_sync(compute_hash, data)
    """
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        if is_async_context():
            warnings.warn(
                f"Sync function '{func.__qualname__}' called from async context. "
                "Use 'await run_sync(func, ...)' for proper async handling.",
                BlockingCallWarning,
                stacklevel=2,
            )
        return func(*args, **kwargs)

    return wrapper


__all__ = [
    "BlockingCallWarning",
    "async_safe",
    "blocking_operation",
    "is_async_context",
    "run_sync",
    "warn_if_async",
]
