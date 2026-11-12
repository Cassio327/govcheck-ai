"""Create the initial GovCheck persistence schema."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid() -> sa.types.TypeEngine:
    return sa.Uuid(as_uuid=True)


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    embedding_type = Vector(384) if dialect == "postgresql" else sa.JSON()

    op.create_table(
        "documents",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("session_id", sa.String(128), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_documents_session_id", "documents", ["session_id"])
    op.create_index("ix_documents_status", "documents", ["status"])
    op.create_index("ix_documents_expires_at", "documents", ["expires_at"])

    op.create_table(
        "pages",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("document_id", _uuid(), sa.ForeignKey("documents.id", ondelete="CASCADE")),
        sa.Column("number", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.UniqueConstraint("document_id", "number"),
    )
    op.create_index("ix_pages_document_id", "pages", ["document_id"])

    op.create_table(
        "chunks",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("document_id", _uuid(), sa.ForeignKey("documents.id", ondelete="CASCADE")),
        sa.Column("page_number", sa.Integer, nullable=False),
        sa.Column("ordinal", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("start_char", sa.Integer, nullable=False),
        sa.Column("end_char", sa.Integer, nullable=False),
        sa.Column("embedding", embedding_type, nullable=False),
        sa.UniqueConstraint("document_id", "ordinal"),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.create_index("ix_chunks_page_number", "chunks", ["page_number"])

    op.create_table(
        "analysis_jobs",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("document_id", _uuid(), sa.ForeignKey("documents.id", ondelete="CASCADE")),
        sa.Column("session_id", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_analysis_jobs_document_id", "analysis_jobs", ["document_id"])
    op.create_index("ix_analysis_jobs_session_id", "analysis_jobs", ["session_id"])
    op.create_index("ix_analysis_jobs_status", "analysis_jobs", ["status"])

    op.create_table(
        "findings",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("document_id", _uuid(), sa.ForeignKey("documents.id", ondelete="CASCADE")),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("evidence_status", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_findings_document_id", "findings", ["document_id"])
    op.create_index("ix_findings_category", "findings", ["category"])
    op.create_index("ix_findings_evidence_status", "findings", ["evidence_status"])

    op.create_table(
        "citations",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("finding_id", _uuid(), sa.ForeignKey("findings.id", ondelete="CASCADE")),
        sa.Column(
            "chunk_id", _uuid(), sa.ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("page_number", sa.Integer, nullable=False),
        sa.Column("excerpt", sa.Text, nullable=False),
    )
    op.create_index("ix_citations_finding_id", "citations", ["finding_id"])

    op.create_table(
        "tool_runs",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("document_id", _uuid(), sa.ForeignKey("documents.id", ondelete="CASCADE")),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("source_url", sa.Text, nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data", sa.JSON, nullable=False),
        sa.Column("error_code", sa.String(128), nullable=True),
    )
    op.create_index("ix_tool_runs_document_id", "tool_runs", ["document_id"])
    op.create_index("ix_tool_runs_status", "tool_runs", ["status"])

    op.create_table(
        "stream_events",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("job_id", _uuid(), sa.ForeignKey("analysis_jobs.id", ondelete="CASCADE")),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("job_id", "sequence"),
    )
    op.create_index("ix_stream_events_job_id", "stream_events", ["job_id"])
    op.create_index("ix_stream_events_event_type", "stream_events", ["event_type"])

    op.create_table(
        "reports",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("document_id", _uuid(), sa.ForeignKey("documents.id", ondelete="CASCADE")),
        sa.Column("markdown", sa.Text, nullable=False),
        sa.Column("json_payload", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_reports_document_id", "reports", ["document_id"])


def downgrade() -> None:
    for table in (
        "reports",
        "stream_events",
        "tool_runs",
        "citations",
        "findings",
        "analysis_jobs",
        "chunks",
        "pages",
        "documents",
    ):
        op.drop_table(table)
