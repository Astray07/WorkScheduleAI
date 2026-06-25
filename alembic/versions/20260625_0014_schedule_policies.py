"""create schedule policies

Revision ID: 20260625_0014
Revises: 20260625_0013
Create Date: 2026-06-25 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260625_0014"
down_revision: str | None = "20260625_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "schedule_policies",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("min_rest_hours", sa.Integer(), nullable=False),
        sa.Column("max_consecutive_shifts", sa.Integer(), nullable=False),
        sa.Column("max_shifts_per_week", sa.Integer(), nullable=False),
        sa.Column("weekend_shift_limit_per_month", sa.Integer(), nullable=False),
        sa.Column("night_shift_limit_per_month", sa.Integer(), nullable=False),
        sa.Column("default_unfilled_requirement_weight", sa.Integer(), nullable=False),
        sa.Column("weight_workload_imbalance", sa.Integer(), nullable=False),
        sa.Column("weight_pair_avoid_violation", sa.Integer(), nullable=False),
        sa.Column("unfilled_policy", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("min_rest_hours >= 0", name="ck_schedule_policies_min_rest"),
        sa.CheckConstraint(
            "max_consecutive_shifts >= 1",
            name="ck_schedule_policies_max_consecutive",
        ),
        sa.CheckConstraint(
            "max_shifts_per_week >= 1",
            name="ck_schedule_policies_max_weekly",
        ),
        sa.CheckConstraint(
            "weekend_shift_limit_per_month >= 0",
            name="ck_schedule_policies_weekend_limit",
        ),
        sa.CheckConstraint(
            "night_shift_limit_per_month >= 0",
            name="ck_schedule_policies_night_limit",
        ),
        sa.CheckConstraint(
            "default_unfilled_requirement_weight >= 0",
            name="ck_schedule_policies_unfilled_weight",
        ),
        sa.CheckConstraint(
            "weight_workload_imbalance >= 0",
            name="ck_schedule_policies_workload_weight",
        ),
        sa.CheckConstraint(
            "weight_pair_avoid_violation >= 0",
            name="ck_schedule_policies_pair_avoid_weight",
        ),
        sa.CheckConstraint(
            "unfilled_policy IN ('soft_penalty')",
            name="ck_schedule_policies_unfilled_policy",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            name="uq_schedule_policies_organization_id",
        ),
    )
    op.create_index(
        "ix_schedule_policies_organization_id",
        "schedule_policies",
        ["organization_id"],
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute('ALTER TABLE "schedule_policies" ENABLE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE "schedule_policies" FORCE ROW LEVEL SECURITY')
        op.execute(
            """
            CREATE POLICY tenant_isolation ON "schedule_policies"
            USING (
                organization_id = current_setting(
                    'app.current_organization_id',
                    true
                )
            )
            WITH CHECK (
                organization_id = current_setting(
                    'app.current_organization_id',
                    true
                )
            )
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute('DROP POLICY IF EXISTS tenant_isolation ON "schedule_policies"')
        op.execute('ALTER TABLE "schedule_policies" NO FORCE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE "schedule_policies" DISABLE ROW LEVEL SECURITY')

    op.drop_index(
        "ix_schedule_policies_organization_id",
        table_name="schedule_policies",
    )
    op.drop_table("schedule_policies")
