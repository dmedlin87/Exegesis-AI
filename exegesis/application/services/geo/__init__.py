"""Geo-related services for Theo Engine.

.. deprecated::
    This module is deprecated. Import from ``exegesis.services.geo``
    instead. This shim exists for backward compatibility.
"""

from __future__ import annotations

import importlib
import warnings
from types import ModuleType

warnings.warn(
    "Importing from exegesis.application.services.geo is deprecated. "
    "Use exegesis.services.geo instead.",
    DeprecationWarning,
    stacklevel=2,
)


_seed_module: ModuleType | None = None


def _load_geo_module() -> ModuleType:
    global _seed_module
    if _seed_module is None:
        _seed_module = importlib.import_module("exegesis.services.geo")
    return _seed_module


def seed_openbible_geo(*args: object, **kwargs: object) -> object:
    """Proxy the service-level loader for OpenBible geography data."""

    module = _load_geo_module()
    return getattr(module, "seed_openbible_geo")(*args, **kwargs)


__all__ = ["seed_openbible_geo"]
