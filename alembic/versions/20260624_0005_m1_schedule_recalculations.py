"""create m1 schedule recalculations

Revision ID: 20260624_0005
Revises: 20260624_0004
Create Date: 2026-06-24 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260624_0005"
down_revision: str | None = "20260624_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "schedule_recalculation_requests",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("schedule_run_id", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("recalculation_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "recalculation_count >= 1 AND recalculation_count <= 3",
            name="ck_schedule_recalculations_count",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_schedule_recalculations_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["schedule_run_id"],
            ["schedule_runs.id"],
            name="fk_schedule_recalculations_schedule_run_id_schedule_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_schedule_recalculation_requests"),
        sa.UniqueConstraint(
            "organization_id",
            "schedule_run_id",
            "idempotency_key",
            name="uq_schedule_recalculations_run_idempotency_key",
        ),
    )
    op.create_index(
        "ix_schedule_recalculations_organization_id",
        "schedule_recalculation_requests",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_schedule_recalculations_schedule_run_id",
        "schedule_recalculation_requests",
        ["schedule_run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_schedule_recalculations_schedule_run_id",
        table_name="schedule_recalculation_requests",
    )
    op.drop_index(
        "ix_schedule_recalculations_organization_id",
        table_name="schedule_recalculation_requests",
    )
    op.drop_table("schedule_recalculation_requests")
