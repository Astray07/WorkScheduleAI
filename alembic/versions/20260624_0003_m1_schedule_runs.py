"""create m1 schedule runs

Revision ID: 20260624_0003
Revises: 20260624_0002
Create Date: 2026-06-24 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260624_0003"
down_revision: str | None = "20260624_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "schedule_runs",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("template", sa.Text(), nullable=False),
        sa.Column("deterministic_mode", sa.Boolean(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("solver_status", sa.Text(), nullable=True),
        sa.Column("solution_quality", sa.Text(), nullable=False),
        sa.Column("current_attempt_no", sa.Integer(), nullable=False),
        sa.Column("recalculation_count", sa.Integer(), nullable=False),
        sa.Column("input_snapshot_hash", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'infeasible', 'failed', 'canceled')",
            name="ck_schedule_runs_status",
        ),
        sa.CheckConstraint(
            "solver_status IS NULL OR solver_status IN ('cp_sat_optimal', 'cp_sat_feasible', 'cp_sat_infeasible', 'cp_sat_model_invalid', 'cp_sat_unknown', 'not_started', 'error')",
            name="ck_schedule_runs_solver_status",
        ),
        sa.CheckConstraint(
            "solution_quality IN ('optimal', 'feasible_not_proven_optimal', 'infeasible', 'unknown')",
            name="ck_schedule_runs_solution_quality",
        ),
        sa.CheckConstraint(
            "template IN ('one_shift_per_day', 'morning_afternoon_night', 'on_call', 'custom')",
            name="ck_schedule_runs_template",
        ),
        sa.CheckConstraint(
            "period_start <= period_end",
            name="ck_schedule_runs_period_order",
        ),
        sa.CheckConstraint(
            "timeout_seconds >= 1 AND timeout_seconds <= 120",
            name="ck_schedule_runs_timeout_seconds",
        ),
        sa.CheckConstraint(
            "current_attempt_no >= 1",
            name="ck_schedule_runs_current_attempt_no",
        ),
        sa.CheckConstraint(
            "recalculation_count >= 0 AND recalculation_count <= 3",
            name="ck_schedule_runs_recalculation_count",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_schedule_runs_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_schedule_runs"),
        sa.UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_schedule_runs_organization_idempotency_key",
        ),
    )
    op.create_index(
        "ix_schedule_runs_organization_id",
        "schedule_runs",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_schedule_runs_organization_period",
        "schedule_runs",
        ["organization_id", "period_start", "period_end"],
        unique=False,
    )
    op.create_table(
        "schedule_input_snapshots",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("schedule_run_id", sa.Text(), nullable=False),
        sa.Column("snapshot_hash", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("storage_uri", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_schedule_input_snapshots_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["schedule_run_id"],
            ["schedule_runs.id"],
            name="fk_schedule_input_snapshots_schedule_run_id_schedule_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_schedule_input_snapshots"),
        sa.UniqueConstraint(
            "schedule_run_id",
            name="uq_schedule_input_snapshots_schedule_run_id",
        ),
    )
    op.create_index(
        "ix_schedule_input_snapshots_organization_id",
        "schedule_input_snapshots",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_schedule_input_snapshots_schedule_run_id",
        "schedule_input_snapshots",
        ["schedule_run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_schedule_input_snapshots_schedule_run_id",
        table_name="schedule_input_snapshots",
    )
    op.drop_index(
        "ix_schedule_input_snapshots_organization_id",
        table_name="schedule_input_snapshots",
    )
    op.drop_table("schedule_input_snapshots")
    op.drop_index("ix_schedule_runs_organization_period", table_name="schedule_runs")
    op.drop_index("ix_schedule_runs_organization_id", table_name="schedule_runs")
    op.drop_table("schedule_runs")
