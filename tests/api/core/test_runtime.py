"""Tests for the application runtime facade."""
from __future__ import annotations

import pytest

from tests.api.core import reload_facade


def test_allow_insecure_startup_requires_non_production_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The runtime facade should restrict insecure startup to dev environments."""

    module = reload_facade("exegesis.application.facades.runtime")
    module.allow_insecure_startup.cache_clear()

    # Clear all env vars that _resolve_environment checks (in priority order)
    for var in (
        "EXEGESIS_ENVIRONMENT",
        "ENVIRONMENT",
        "EXEGESIS_PROFILE",
    ):
        monkeypatch.delenv(var, raising=False)

    monkeypatch.setenv("EXEGESIS_ALLOW_INSECURE_STARTUP", "true")
    monkeypatch.setenv("EXEGESIS_ENVIRONMENT", "development")
    assert module.allow_insecure_startup() is True

    module.allow_insecure_startup.cache_clear()
    monkeypatch.setenv("EXEGESIS_ENVIRONMENT", "production")
    with pytest.raises(RuntimeError):
        module.allow_insecure_startup()
