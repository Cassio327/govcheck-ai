"""Allow at most one active analysis per anonymous session."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    active = sa.text("status IN ('pending', 'running')")
    # A deployment cannot safely resume in-process background tasks from the
    # previous release. Fail them closed before adding the invariant, which also
    # makes upgrades deterministic if an older version admitted duplicates.
    op.execute(
        sa.text("UPDATE analysis_jobs SET status = 'failed' WHERE status IN ('pending', 'running')")
    )
    op.create_index(
        "uq_analysis_jobs_active_session",
        "analysis_jobs",
        ["session_id"],
        unique=True,
        postgresql_where=active,
        sqlite_where=active,
    )


def downgrade() -> None:
    op.drop_index("uq_analysis_jobs_active_session", table_name="analysis_jobs")
