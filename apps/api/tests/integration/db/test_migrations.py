import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def test_initial_migration_creates_complete_persistence_schema(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    security_logger = logging.getLogger("govcheck.security")
    security_logger.disabled = False
    database_path = tmp_path / "migration.db"
    config = Config("alembic.ini")
    config.set_main_option("script_location", "migrations")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database_path}")

    command.upgrade(config, "head")

    assert security_logger.disabled is False

    engine = create_engine(f"sqlite:///{database_path}")
    tables = set(inspect(engine).get_table_names())
    assert tables == {
        "alembic_version",
        "analysis_jobs",
        "chunks",
        "citations",
        "documents",
        "findings",
        "pages",
        "reports",
        "stream_events",
        "tool_runs",
    }
    tool_run_columns = {column["name"] for column in inspect(engine).get_columns("tool_runs")}
    assert "request" in tool_run_columns
    analysis_indexes = {item["name"]: item for item in inspect(engine).get_indexes("analysis_jobs")}
    assert analysis_indexes["uq_analysis_jobs_active_session"]["unique"] == 1

    command.downgrade(config, "base")
    assert inspect(engine).get_table_names() == ["alembic_version"]


def test_active_job_migration_fails_closed_for_preexisting_running_jobs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    database_path = tmp_path / "preexisting-jobs.db"
    config = Config("alembic.ini")
    config.set_main_option("script_location", "migrations")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database_path}")
    command.upgrade(config, "0002")
    engine = create_engine(f"sqlite:///{database_path}")
    now = datetime.now(UTC)
    document_id = uuid4().hex
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO documents
                    (id, session_id, filename, status, created_at, expires_at)
                VALUES
                    (:id, 'duplicate-session', 'edital.pdf', 'indexed', :created, :expires)
                """
            ),
            {
                "id": document_id,
                "created": now.isoformat(),
                "expires": (now + timedelta(hours=1)).isoformat(),
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO analysis_jobs
                    (id, document_id, session_id, status, created_at)
                VALUES
                    (:first, :document_id, 'duplicate-session', 'running', :created),
                    (:second, :document_id, 'duplicate-session', 'pending', :created)
                """
            ),
            {
                "first": uuid4().hex,
                "second": uuid4().hex,
                "document_id": document_id,
                "created": now.isoformat(),
            },
        )

    command.upgrade(config, "head")

    with engine.connect() as connection:
        statuses = (
            connection.execute(text("SELECT status FROM analysis_jobs ORDER BY id")).scalars().all()
        )
    assert statuses == ["failed", "failed"]
    analysis_indexes = {item["name"]: item for item in inspect(engine).get_indexes("analysis_jobs")}
    assert analysis_indexes["uq_analysis_jobs_active_session"]["unique"] == 1
