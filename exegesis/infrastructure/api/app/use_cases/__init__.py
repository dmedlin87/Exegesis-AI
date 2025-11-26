"""Application use cases orchestrating business logic.

.. deprecated::
    This module is deprecated. Import from ``exegesis.application.use_cases``
    instead. This shim exists for backward compatibility.
"""

import warnings

from exegesis.application.use_cases import RefreshDiscoveriesUseCase

warnings.warn(
    "Importing from exegesis.infrastructure.api.app.use_cases is deprecated. "
    "Use exegesis.application.use_cases instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["RefreshDiscoveriesUseCase"]
