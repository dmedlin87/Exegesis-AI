"""Tests for the application database facade."""
from __future__ import annotations

from contextlib import closing, contextmanager

from sqlalchemy import text

from exegesis.application.facades import database as facades_database


@contextmanager
def _isolated_database_state():
    """Context manager that saves and restores database global state."""
    # Save original state
    original_engine = facades_database._engine
    original_session_local = facades_database._SessionLocal
    original_url_override = facades_database._engine_url_override

    # Clear for test isolation
    facades_database._engine = None
    facades_database._SessionLocal = None
    facades_database._engine_url_override = None

    try:
        yield
    finally:
        # Restore original state
        facades_database._engine = original_engine
        facades_database._SessionLocal = original_session_local
        facades_database._engine_url_override = original_url_override


def test_database_facade_configures_engine_and_sessions() -> None:
    """The database facade should manage the engine and session lifecycle."""

    with _isolated_database_state():
        engine = facades_database.configure_engine("sqlite:///:memory:")
        try:
            assert str(engine.url) == "sqlite:///:memory:"
            assert facades_database.get_engine() is engine

            session_gen = facades_database.get_session()
            with closing(next(session_gen)) as session:
                result = session.execute(text("SELECT 1")).scalar_one()
                assert result == 1
        finally:
            engine.dispose()
