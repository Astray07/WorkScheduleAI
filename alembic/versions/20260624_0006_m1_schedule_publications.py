"""create m1 schedule publications

Revision ID: 20260624_0006
Revises: 20260624_0005
Create Date: 2026-06-24 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260624_0006"
down_revision: str | None = "20260624_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "schedule_publications",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("schedule_run_id", sa.Text(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("assignment_snapshot_hash", sa.Text(), nullable=False),
        sa.Column("issue_snapshot_hash", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('published', 'archived')",
            name="ck_schedule_publications_status",
        ),
        sa.CheckConstraint(
            "period_start <= period_end",
            name="ck_schedule_publications_period_order",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_schedule_publications_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["schedule_run_id"],
            ["schedule_runs.id"],
            name="fk_schedule_publications_schedule_run_id_schedule_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_schedule_publications"),
        sa.UniqueConstraint(
            "schedule_run_id",
            name="uq_schedule_publications_schedule_run_id",
        ),
    )
    op.create_index(
        "ix_schedule_publications_organization_id",
        "schedule_publications",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_schedule_publications_schedule_run_id",
        "schedule_publications",
        ["schedule_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_schedule_publications_organization_period",
        "schedule_publications",
        ["organization_id", "period_start", "period_end"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_schedule_publications_organization_period",
        table_name="schedule_publications",
    )
    op.drop_index(
        "ix_schedule_publications_schedule_run_id",
        table_name="schedule_publications",
    )
    op.drop_index(
        "ix_schedule_publications_organization_id",
        table_name="schedule_publications",
    )
    op.drop_table("schedule_publications")
