"""Create the evidence_dossiers table."""
from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session


def _table_exists(connection: Connection) -> bool:
    inspector = inspect(connection)
    return "evidence_dossiers" in inspector.get_table_names()


def _dialect_settings(connection: Connection) -> tuple[str, str, str, str, str, str]:
    dialect = connection.dialect.name
    if dialect == "postgresql":
        return (
            "JSONB",
            "'{}'::jsonb",
            "'[]'::jsonb",
            "TIMESTAMPTZ",
            "now()",
            "DOUBLE PRECISION",
        )
    return "JSON", "'{}'", "'[]'", "TIMESTAMP", "CURRENT_TIMESTAMP", "REAL"


def _create_table(connection: Connection) -> None:
    (
        json_type,
        json_object_default,
        json_array_default,
        timestamp_type,
        timestamp_default,
        confidence_type,
    ) = _dialect_settings(connection)
    connection.exec_driver_sql(
        f"""CREATE TABLE evidence_dossiers (
            id TEXT PRIMARY KEY,
            verse_ref TEXT NOT NULL,
            claim TEXT NOT NULL,
            confidence_score {confidence_type} NOT NULL,
            created_at {timestamp_type} NOT NULL DEFAULT {timestamp_default},
            last_updated {timestamp_type} NOT NULL DEFAULT {timestamp_default},
            textual_analysis {json_type} NOT NULL DEFAULT {json_object_default},
            logical_analysis {json_type} NOT NULL DEFAULT {json_object_default},
            scientific_analysis {json_type} NOT NULL DEFAULT {json_object_default},
            cultural_analysis {json_type} NOT NULL DEFAULT {json_object_default},
            primary_sources {json_type} NOT NULL DEFAULT {json_array_default},
            secondary_sources {json_type} NOT NULL DEFAULT {json_array_default},
            tertiary_sources {json_type} NOT NULL DEFAULT {json_array_default},
            competing_hypotheses {json_type} NOT NULL DEFAULT {json_array_default},
            metadata {json_type}
        )"""
    )


def _ensure_index(connection: Connection) -> None:
    inspector = inspect(connection)
    existing_indexes = {index["name"] for index in inspector.get_indexes("evidence_dossiers")}
    if "ix_evidence_dossiers_verse_ref" in existing_indexes:
        return
    connection.exec_driver_sql(
        "CREATE INDEX ix_evidence_dossiers_verse_ref ON evidence_dossiers (verse_ref)"
    )


def upgrade(*, session: Session, engine: Engine) -> None:  # pragma: no cover - executed via migration runner
    bind = session.get_bind()
    if isinstance(bind, Connection):
        connection = bind
        close_connection = False
    else:
        connection = engine.connect()
        close_connection = True
    try:
        if not _table_exists(connection):
            _create_table(connection)
        _ensure_index(connection)
    finally:
        if close_connection:
            connection.close()
    session.flush()
