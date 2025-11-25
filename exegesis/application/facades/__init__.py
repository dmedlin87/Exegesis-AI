"""Compatibility facades exposing application-layer entry points.

These modules provide forward-looking import paths for adapters while the
legacy implementation continues to live under ``theo.infrastructure``. Once the
migration completes, adapters can depend exclusively on the application
package without touching infrastructure-specific modules.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "database",
    "research",
    "events",
    "runtime",
    "secret_migration",
    "settings",
    "settings_store",
    "version",
    "Base",
    "configure_engine",
    "get_engine",
    "get_session",
    "allow_insecure_startup",
    "ResearchService",
    "ResearchNoteDraft",
    "ResearchNoteEvidenceDraft",
    "get_research_service",
    "migrate_secret_settings",
    "Settings",
    "get_settings",
    "get_settings_secret",
    "get_settings_cipher",
    "get_event_publisher",
    "reset_event_publisher_cache",
    "SETTINGS_NAMESPACE",
    "SettingNotFoundError",
    "load_setting",
    "require_setting",
    "save_setting",
    "get_git_sha",
]

_MODULE_EXPORTS = {
    "database": "exegesis.application.facades.database",
    "research": "exegesis.application.facades.research",
    "events": "exegesis.application.facades.events",
    "runtime": "exegesis.application.facades.runtime",
    "secret_migration": "exegesis.application.facades.secret_migration",
    "settings": "exegesis.application.facades.settings",
    "settings_store": "exegesis.application.facades.settings_store",
    "version": "exegesis.application.facades.version",
}

_ATTRIBUTE_EXPORTS = {
    "Base": ("exegesis.application.facades.database", "Base"),
    "configure_engine": ("exegesis.application.facades.database", "configure_engine"),
    "get_engine": ("exegesis.application.facades.database", "get_engine"),
    "get_session": ("exegesis.application.facades.database", "get_session"),
    "allow_insecure_startup": (
        "exegesis.application.facades.runtime",
        "allow_insecure_startup",
    ),
    "ResearchService": (
        "exegesis.application.facades.research",
        "ResearchService",
    ),
    "ResearchNoteDraft": (
        "exegesis.application.facades.research",
        "ResearchNoteDraft",
    ),
    "ResearchNoteEvidenceDraft": (
        "exegesis.application.facades.research",
        "ResearchNoteEvidenceDraft",
    ),
    "get_event_publisher": (
        "exegesis.application.facades.events",
        "get_event_publisher",
    ),
    "reset_event_publisher_cache": (
        "exegesis.application.facades.events",
        "reset_event_publisher_cache",
    ),
    "get_research_service": (
        "exegesis.application.facades.research",
        "get_research_service",
    ),
    "migrate_secret_settings": (
        "exegesis.application.facades.secret_migration",
        "migrate_secret_settings",
    ),
    "Settings": ("exegesis.application.facades.settings", "Settings"),
    "get_settings": ("exegesis.application.facades.settings", "get_settings"),
    "get_settings_secret": (
        "exegesis.application.facades.settings",
        "get_settings_secret",
    ),
    "get_settings_cipher": (
        "exegesis.application.facades.settings",
        "get_settings_cipher",
    ),
    "SETTINGS_NAMESPACE": (
        "exegesis.application.facades.settings_store",
        "SETTINGS_NAMESPACE",
    ),
    "SettingNotFoundError": (
        "exegesis.application.facades.settings_store",
        "SettingNotFoundError",
    ),
    "load_setting": ("exegesis.application.facades.settings_store", "load_setting"),
    "require_setting": (
        "exegesis.application.facades.settings_store",
        "require_setting",
    ),
    "save_setting": ("exegesis.application.facades.settings_store", "save_setting"),
    "get_git_sha": ("exegesis.application.facades.version", "get_git_sha"),
}


def __getattr__(name: str) -> Any:
    if name in _MODULE_EXPORTS:
        module = import_module(_MODULE_EXPORTS[name])
        globals()[name] = module
        return module
    if name in _ATTRIBUTE_EXPORTS:
        module_name, attribute = _ATTRIBUTE_EXPORTS[name]
        module = import_module(module_name)
        value = getattr(module, attribute)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
