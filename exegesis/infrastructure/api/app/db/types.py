"""Backward-compatible shim for relocated database type decorators."""
from __future__ import annotations

from warnings import warn

warn(
    "exegesis.infrastructure.api.app.db.types is deprecated; import from "
    "exegesis.adapters.persistence.types instead",
    DeprecationWarning,
    stacklevel=2,
)

from exegesis.adapters.persistence.types import *  # noqa: F401,F403
from exegesis.adapters.persistence.types import __all__ as __all__  # type: ignore
