"""Tests for runtime startup guards."""

from __future__ import annotations

import pytest

from exegesis.application.facades import runtime


@pytest.fixture(autouse=True)
def clear_runtime_cache() -> None:
    """Ensure cached runtime checks are reset between tests."""

    runtime.allow_insecure_startup.cache_clear()
    yield
    runtime.allow_insecure_startup.cache_clear()


def test_allow_insecure_startup_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without the override flag, insecure startup is not permitted."""

    monkeypatch.delenv("EXEGESIS_ALLOW_INSECURE_STARTUP", raising=False)
    monkeypatch.setenv("EXEGESIS_ENVIRONMENT", "development")

    assert runtime.allow_insecure_startup() is False


def test_allow_insecure_startup_allowed_in_development(monkeypatch: pytest.MonkeyPatch) -> None:
    """Setting the override works when environment is development."""

    monkeypatch.setenv("EXEGESIS_ALLOW_INSECURE_STARTUP", "1")
    monkeypatch.setenv("EXEGESIS_ENVIRONMENT", "development")

    assert runtime.allow_insecure_startup() is True


def test_allow_insecure_startup_rejected_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production environments cannot enable the override."""

    monkeypatch.setenv("EXEGESIS_ALLOW_INSECURE_STARTUP", "true")
    monkeypatch.setenv("EXEGESIS_ENVIRONMENT", "production")

    with pytest.raises(RuntimeError):
        runtime.allow_insecure_startup()


def test_resolve_environment_prefers_EXEGESIS_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    """EXEGESIS_ENVIRONMENT should take precedence over other environment hints."""

    for name in [
        "EXEGESIS_ENVIRONMENT",
        "EXEGESIS_ENVIRONMENT",
        "ENVIRONMENT",
        "EXEGESIS_PROFILE",
    ]:
        monkeypatch.delenv(name, raising=False)

    monkeypatch.setenv("EXEGESIS_ENVIRONMENT", " Development ")
    monkeypatch.setenv("EXEGESIS_ENVIRONMENT", "staging")
    monkeypatch.setenv("ENVIRONMENT", "qa")
    monkeypatch.setenv("EXEGESIS_PROFILE", "local")

    assert runtime._resolve_environment() == "development"


def test_resolve_environment_uses_profile_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """When other variables are unset, EXEGESIS_PROFILE should be used."""

    for name in [
        "EXEGESIS_ENVIRONMENT",
        "EXEGESIS_ENVIRONMENT",
        "ENVIRONMENT",
        "EXEGESIS_PROFILE",
    ]:
        monkeypatch.delenv(name, raising=False)

    monkeypatch.setenv("EXEGESIS_PROFILE", "Local")

    assert runtime._resolve_environment() == "local"


def test_resolve_environment_defaults_to_production(monkeypatch: pytest.MonkeyPatch) -> None:
    """If no environment variables are set, fall back to the production label."""

    for name in [
        "EXEGESIS_ENVIRONMENT",
        "EXEGESIS_ENVIRONMENT",
        "ENVIRONMENT",
        "EXEGESIS_PROFILE",
    ]:
        monkeypatch.delenv(name, raising=False)

    assert runtime._resolve_environment() == "production"


def test_current_runtime_environment_exposes_resolved_label(monkeypatch: pytest.MonkeyPatch) -> None:
    """Expose the same label used by allow_insecure_startup for diagnostics."""

    for name in [
        "EXEGESIS_ENVIRONMENT",
        "EXEGESIS_ENVIRONMENT",
        "ENVIRONMENT",
        "EXEGESIS_PROFILE",
    ]:
        monkeypatch.delenv(name, raising=False)

    monkeypatch.setenv("EXEGESIS_ENVIRONMENT", "Staging")

    assert runtime.current_runtime_environment() == "staging"
