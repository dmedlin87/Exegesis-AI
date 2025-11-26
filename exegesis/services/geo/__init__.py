"""Geospatial data seeding services.

This module contains infrastructure-level services for loading
geospatial reference data into the database.
"""

from .seed_openbible_geo import seed_openbible_geo

__all__ = ["seed_openbible_geo"]
