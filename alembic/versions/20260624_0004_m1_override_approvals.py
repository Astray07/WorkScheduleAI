"""create m1 override approvals

Revision ID: 20260624_0004
Revises: 20260624_0003
Create Date: 2026-06-24 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260624_0004"
down_revision: str | None = "20260624_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "override_approvals",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("schedule_run_id", sa.Text(), nullable=False),
        sa.Column("relaxation_proposal_id", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("notification_required", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "type IN ('approve_time_off_override', 'approve_pair_constraint_override', 'approve_min_rest_override', 'keep_unfilled_requirement', 'reduce_role_requirement', 'mark_manual_review')",
            name="ck_override_approvals_type",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_override_approvals_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["schedule_run_id"],
            ["schedule_runs.id"],
            name="fk_override_approvals_schedule_run_id_schedule_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_override_approvals"),
        sa.UniqueConstraint(
            "organization_id",
            "schedule_run_id",
            "relaxation_proposal_id",
            name="uq_override_approvals_run_proposal",
        ),
    )
    op.create_index(
        "ix_override_approvals_organization_id",
        "override_approvals",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_override_approvals_schedule_run_id",
        "override_approvals",
        ["schedule_run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_override_approvals_schedule_run_id",
        table_name="override_approvals",
    )
    op.drop_index(
        "ix_override_approvals_organization_id",
        table_name="override_approvals",
    )
    op.drop_table("override_approvals")
