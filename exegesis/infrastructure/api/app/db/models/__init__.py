"""Backward-compatible shims for relocated persistence models."""
from __future__ import annotations

from warnings import warn

warn(
    "exegesis.infrastructure.api.app.db.models is deprecated; import from "
    "exegesis.adapters.persistence.models instead",
    DeprecationWarning,
    stacklevel=2,
)

from exegesis.infrastructure.api.app.persistence_models import *  # noqa: F401,F403
from exegesis.infrastructure.api.app.persistence_models import __all__ as __all__  # type: ignore

from .dossier import EvidenceDossier  # noqa: F401

__all__ += ["EvidenceDossier"]
