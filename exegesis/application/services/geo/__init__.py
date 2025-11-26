"""Geo-related services for Theo Engine.

.. deprecated::
    This module is deprecated. Import from ``exegesis.services.geo``
    instead. This shim exists for backward compatibility.
"""

import warnings

from exegesis.services.geo import seed_openbible_geo

warnings.warn(
    "Importing from exegesis.application.services.geo is deprecated. "
    "Use exegesis.services.geo instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["seed_openbible_geo"]
