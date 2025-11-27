"""Comprehensive coverage for exegesis.infrastructure.api.app.core."""

from __future__ import annotations

import importlib
import re
import sqlite3
import sys
import tempfile
import warnings
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import given, settings as hypothesis_settings, strategies as st
from pydantic_core import ValidationError as PydanticValidationError
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session as OrmSession

from exegesis.application.facades import database as database_module
from exegesis.application.facades import runtime as runtime_facade

warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    module="theo.infrastructure.api.app.core",
)


def _ensure_theo_core_aliases() -> None:
    hierarchy = [
        "theo",
        "theo.infrastructure",
        "theo.infrastructure.api",
        "theo.infrastructure.api.app",
        "theo.infrastructure.api.app.core",
    ]
    for package in hierarchy:
        if package not in sys.modules:
            module = ModuleType(package)
            module.__path__ = []
            sys.modules[package] = module
            parent = package.rpartition(".")[0]
            if parent and parent in sys.modules:
                setattr(sys.modules[parent], package.split(".")[-1], module)

    for name in ("database", "settings", "runtime"):
        target = importlib.import_module(f"exegesis.infrastructure.api.app.core.{name}")
        alias_name = f"theo.infrastructure.api.app.core.{name}"
        sys.modules[alias_name] = target
        setattr(sys.modules["theo.infrastructure.api.app.core"], name, target)


_ensure_theo_core_aliases()

from theo.infrastructure.api.app.core import database as core_database
from theo.infrastructure.api.app.core import runtime as core_runtime
from theo.infrastructure.api.app.core import settings as core_settings

HYPOTHESIS_SETTINGS = hypothesis_settings(max_examples=40, deadline=None)


def test_core_database_reexports_facade() -> None:
    assert core_database.configure_engine is database_module.configure_engine


@pytest.mark.usefixtures("reset_global_state")
def test_configure_engine_recreates_engine_when_url_changes(tmp_path: Path) -> None:
    first_db = tmp_path / "first.db"
    second_db = tmp_path / "second.db"
    first_engine = database_module.configure_engine(f"sqlite:///{first_db}")
    assert first_engine is database_module.get_engine()
    second_engine = database_module.configure_engine(f"sqlite:///{second_db}")
    assert second_engine is database_module.get_engine()
    assert second_engine is not first_engine
    assert str(database_module._engine.url).startswith("sqlite")


@pytest.mark.usefixtures("reset_global_state")
def test_session_close_suppresses_sqlite_closed_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    database_module.configure_engine("sqlite:///:memory:")
    session_generator = database_module.get_session()
    session = next(session_generator)
    session.get_bind = MagicMock(return_value=database_module.get_engine())
    close_exc = sqlite3.ProgrammingError("database is closed")
    programming_error = ProgrammingError("SELECT 1", {}, close_exc)

    def _raise_close(self) -> None:  # type: ignore[override]
        raise programming_error

    monkeypatch.setattr(OrmSession, "close", _raise_close, raising=True)
    dispose_mock = MagicMock()
    monkeypatch.setattr(database_module, "dispose_sqlite_engine", dispose_mock)
    debug_logger = MagicMock()
    monkeypatch.setattr(database_module._LOGGER, "debug", debug_logger)

    session_generator.close()

    dispose_mock.assert_called_once_with(database_module.get_engine(), dispose_engine=False)
    debug_logger.assert_called_once()


@pytest.mark.usefixtures("reset_global_state")
def test_session_close_reraises_unexpected_programming_error(monkeypatch: pytest.MonkeyPatch) -> None:
    database_module.configure_engine("sqlite:///:memory:")
    session_generator = database_module.get_session()
    session = next(session_generator)
    session.get_bind = MagicMock(return_value=database_module.get_engine())
    pool_error = ProgrammingError(
        "SELECT 1",
        {},
        sqlite3.ProgrammingError("connection pool exhausted"),
    )

    def _raise_close_error(self) -> None:  # type: ignore[override]
        raise pool_error

    monkeypatch.setattr(OrmSession, "close", _raise_close_error, raising=True)
    warning_logger = MagicMock()
    monkeypatch.setattr(database_module._LOGGER, "warning", warning_logger)
    monkeypatch.setattr(database_module, "dispose_sqlite_engine", MagicMock())

    with pytest.raises(ProgrammingError):
        session_generator.close()

    warning_logger.assert_called_once()


@pytest.mark.usefixtures("reset_global_state")
def test_transaction_rolls_back_when_exception_occurs(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'txn.db'}"
    engine = database_module.configure_engine(url)
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS rollback_test"))
        conn.execute(text("CREATE TABLE rollback_test (id INTEGER PRIMARY KEY, value TEXT)"))
        conn.commit()

    session_generator = database_module.get_session()
    session = next(session_generator)
    with pytest.raises(RuntimeError):
        session.execute(text("INSERT INTO rollback_test (value) VALUES ('rolled back')"))
        raise RuntimeError("trigger rollback")
    session_generator.close()

    second_gen = database_module.get_session()
    second_session = next(second_gen)
    result = second_session.execute(text("SELECT COUNT(*) FROM rollback_test")).scalar_one()
    assert result == 0
    second_gen.close()


@pytest.mark.asyncio
@pytest.mark.usefixtures("reset_global_state")
async def test_run_db_sync_delegates_to_async_utils(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_run_sync = AsyncMock(return_value="ok")
    monkeypatch.setattr(
        "exegesis.application.core.async_utils.run_sync",
        fake_run_sync,
    )

    result = await database_module.run_db_sync(lambda value: value + 1, 5)

    assert result == "ok"
    fake_run_sync.assert_awaited_once()


@st.composite
def _reranker_config(draw) -> tuple[str, str, str, str | None, str | None, bool]:
    reranker_enabled = draw(st.booleans())
    path_kind = draw(st.sampled_from(["none", "relative", "absolute_inside", "absolute_outside"]))
    relative_segment = draw(st.text(alphabet=st.characters(min_codepoint=97, max_codepoint=122), min_size=1, max_size=8))
    registry_uri = draw(
        st.one_of(
            st.none(),
            st.text(min_size=5, max_size=20, alphabet=st.characters(min_codepoint=97, max_codepoint=122)),
        )
    )
    include_sha = draw(st.booleans())
    sha_value: str | None = None
    valid_sha = False
    if include_sha:
        valid_sha = draw(st.booleans())
        if valid_sha:
            sha_value = draw(st.from_regex(r"[0-9a-fA-F]{64}", fullmatch=True))
        else:
            sha_value = draw(
                st.text(min_size=1, max_size=70).filter(
                    lambda candidate: re.fullmatch(r"[0-9a-fA-F]{64}", candidate) is None
                )
            )
    return reranker_enabled, path_kind, relative_segment, registry_uri, sha_value, valid_sha


@HYPOTHESIS_SETTINGS
@given(config=_reranker_config())
def test_settings_reranker_validation_with_combinations(
    config: tuple[str, str, str, str | None, str | None, bool],
) -> None:
    (
        reranker_enabled,
        path_kind,
        relative_segment,
        registry_uri,
        sha_value,
        sha_valid,
    ) = config
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_root = Path(tmpdir)
        overrides: dict[str, object] = {
            "storage_root": storage_root,
            "reranker_enabled": reranker_enabled,
        }

        path_value: Path | None = None
        if path_kind == "none":
            path_value = None
        elif path_kind == "relative":
            path_value = Path(relative_segment)
        elif path_kind == "absolute_inside":
            path_value = (storage_root / "rerankers" / relative_segment).resolve()
        else:
            path_value = (storage_root.parent / "outside" / relative_segment).resolve()

        overrides["reranker_model_path"] = path_value

        if registry_uri is not None:
            overrides["reranker_model_registry_uri"] = registry_uri

        if sha_value is not None:
            overrides["reranker_model_sha256"] = sha_value

        should_fail = False
        if reranker_enabled:
            if registry_uri and path_value:
                should_fail = True
            elif registry_uri and sha_value:
                should_fail = True
            elif not path_value and sha_value:
                should_fail = True
            elif path_value and not sha_value:
                should_fail = True
            elif path_kind == "absolute_outside":
                should_fail = True
            elif sha_value and not sha_valid:
                should_fail = True

        exception_raised = False
        try:
            settings_instance = core_settings.Settings(**overrides)
        except (ValueError, PydanticValidationError):
            exception_raised = True
        else:
            if reranker_enabled and path_value and sha_value and sha_valid and not should_fail:
                assert settings_instance.reranker_model_sha256 == sha_value.lower()
                assert "rerankers" in str(settings_instance.reranker_model_path)

        assert exception_raised is should_fail


def _clear_runtime_state() -> None:
    runtime_facade.allow_insecure_startup.cache_clear()
    runtime_facade.clear_generated_dev_key()


def test_is_development_environment_detects_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_runtime_state()
    monkeypatch.setenv("EXEGESIS_ENVIRONMENT", "TeStInG")
    monkeypatch.setenv("EXEGESIS_ALLOW_INSECURE_STARTUP", "0")

    assert runtime_facade.is_development_environment()
    assert runtime_facade.current_runtime_environment() == "testing"


def test_allow_insecure_startup_raises_outside_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_runtime_state()
    monkeypatch.setenv("EXEGESIS_ENVIRONMENT", "production")
    monkeypatch.setenv("EXEGESIS_ALLOW_INSECURE_STARTUP", "true")

    with pytest.raises(RuntimeError):
        core_runtime.allow_insecure_startup()


def test_allow_insecure_startup_allows_development(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_runtime_state()
    monkeypatch.setenv("EXEGESIS_ENVIRONMENT", "development")
    monkeypatch.setenv("EXEGESIS_ALLOW_INSECURE_STARTUP", "1")

    assert core_runtime.allow_insecure_startup()


def test_generate_ephemeral_dev_key_caches_and_clears(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_runtime_state()
    monkeypatch.setenv("EXEGESIS_ENVIRONMENT", "development")

    first_key = runtime_facade.generate_ephemeral_dev_key()
    assert first_key is not None and first_key.startswith("dev-")

    assert runtime_facade.get_generated_dev_key() == first_key
    assert runtime_facade.generate_ephemeral_dev_key() == first_key

    runtime_facade.clear_generated_dev_key()
    assert runtime_facade.get_generated_dev_key() is None
