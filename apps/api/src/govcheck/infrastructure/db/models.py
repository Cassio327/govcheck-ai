from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import Mapped, mapped_column, relationship

from govcheck.infrastructure.db.base import Base

UUID_PK = sa.Uuid(as_uuid=True)


class DocumentRecord(Base):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(UUID_PK, primary_key=True, default=uuid4)
    session_id: Mapped[str] = mapped_column(sa.String(128), index=True)
    filename: Mapped[str] = mapped_column(sa.String(255))
    status: Mapped[str] = mapped_column(sa.String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), index=True)


class PageRecord(Base):
    __tablename__ = "pages"
    __table_args__ = (sa.UniqueConstraint("document_id", "number"),)

    id: Mapped[UUID] = mapped_column(UUID_PK, primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        UUID_PK, sa.ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    number: Mapped[int] = mapped_column(sa.Integer)
    text: Mapped[str] = mapped_column(sa.Text)


class ChunkRecord(Base):
    __tablename__ = "chunks"
    __table_args__ = (sa.UniqueConstraint("document_id", "ordinal"),)

    id: Mapped[UUID] = mapped_column(UUID_PK, primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        UUID_PK, sa.ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    page_number: Mapped[int] = mapped_column(sa.Integer, index=True)
    ordinal: Mapped[int] = mapped_column(sa.Integer)
    text: Mapped[str] = mapped_column(sa.Text)
    start_char: Mapped[int] = mapped_column(sa.Integer)
    end_char: Mapped[int] = mapped_column(sa.Integer)
    embedding: Mapped[list[float]] = mapped_column(Vector(384).with_variant(sa.JSON(), "sqlite"))


class AnalysisJobRecord(Base):
    __tablename__ = "analysis_jobs"
    __table_args__ = (
        sa.Index(
            "uq_analysis_jobs_active_session",
            "session_id",
            unique=True,
            postgresql_where=sa.text("status IN ('pending', 'running')"),
            sqlite_where=sa.text("status IN ('pending', 'running')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(UUID_PK, primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        UUID_PK, sa.ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    session_id: Mapped[str] = mapped_column(sa.String(128), index=True)
    status: Mapped[str] = mapped_column(sa.String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))


class FindingRecord(Base):
    __tablename__ = "findings"

    id: Mapped[UUID] = mapped_column(UUID_PK, primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        UUID_PK, sa.ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(sa.String(32), index=True)
    title: Mapped[str] = mapped_column(sa.String(255))
    value: Mapped[str] = mapped_column(sa.Text)
    evidence_status: Mapped[str] = mapped_column(sa.String(32), index=True)
    confidence: Mapped[float] = mapped_column(sa.Float)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    citations: Mapped[list["CitationRecord"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="CitationRecord.page_number"
    )


class CitationRecord(Base):
    __tablename__ = "citations"

    id: Mapped[UUID] = mapped_column(UUID_PK, primary_key=True, default=uuid4)
    finding_id: Mapped[UUID] = mapped_column(
        UUID_PK, sa.ForeignKey("findings.id", ondelete="CASCADE"), index=True
    )
    chunk_id: Mapped[UUID | None] = mapped_column(
        UUID_PK, sa.ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True
    )
    page_number: Mapped[int] = mapped_column(sa.Integer)
    excerpt: Mapped[str] = mapped_column(sa.Text)


class ToolRunRecord(Base):
    __tablename__ = "tool_runs"

    id: Mapped[UUID] = mapped_column(UUID_PK, primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        UUID_PK, sa.ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(sa.String(128))
    status: Mapped[str] = mapped_column(sa.String(32), index=True)
    request: Mapped[dict[str, Any]] = mapped_column(sa.JSON, default=dict)
    source_url: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    data: Mapped[dict[str, Any]] = mapped_column(sa.JSON, default=dict)
    error_code: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)


class StreamEventRecord(Base):
    __tablename__ = "stream_events"
    __table_args__ = (sa.UniqueConstraint("job_id", "sequence"),)

    id: Mapped[UUID] = mapped_column(UUID_PK, primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(
        UUID_PK, sa.ForeignKey("analysis_jobs.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(sa.Integer)
    event_type: Mapped[str] = mapped_column(sa.String(128), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(sa.JSON)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))


class ReportRecord(Base):
    __tablename__ = "reports"

    id: Mapped[UUID] = mapped_column(UUID_PK, primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        UUID_PK, sa.ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    markdown: Mapped[str] = mapped_column(sa.Text)
    json_payload: Mapped[dict[str, Any]] = mapped_column(sa.JSON)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
