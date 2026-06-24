"""create m1 solver diagnostic events

Revision ID: 20260624_0010
Revises: 20260624_0009
Create Date: 2026-06-24 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260624_0010"
down_revision: str | None = "20260624_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "solver_diagnostic_events",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("schedule_run_id", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("shift_slot_id", sa.Text(), nullable=True),
        sa.Column("role_id", sa.Text(), nullable=True),
        sa.Column("employee_id", sa.Text(), nullable=True),
        sa.Column("related_employee_ids_json", sa.Text(), nullable=False),
        sa.Column("constraint_type", sa.Text(), nullable=False),
        sa.Column("constraint_id", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["schedule_run_id"],
            ["schedule_runs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["shift_slot_id"],
            ["shift_slots.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_solver_diagnostics_organization_id",
        "solver_diagnostic_events",
        ["organization_id"],
    )
    op.create_index(
        "ix_solver_diagnostics_schedule_run_id",
        "solver_diagnostic_events",
        ["schedule_run_id"],
    )
    op.create_index(
        "ix_solver_diagnostics_shift_slot_id",
        "solver_diagnostic_events",
        ["shift_slot_id"],
    )
    op.create_index(
        "ix_solver_diagnostics_role_id",
        "solver_diagnostic_events",
        ["role_id"],
    )
    op.create_index(
        "ix_solver_diagnostics_employee_id",
        "solver_diagnostic_events",
        ["employee_id"],
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            'ALTER TABLE "solver_diagnostic_events" ENABLE ROW LEVEL SECURITY'
        )
        op.execute(
            'ALTER TABLE "solver_diagnostic_events" FORCE ROW LEVEL SECURITY'
        )
        op.execute(
            """
            CREATE POLICY tenant_isolation ON "solver_diagnostic_events"
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
        op.execute(
            'DROP POLICY IF EXISTS tenant_isolation ON "solver_diagnostic_events"'
        )
        op.execute(
            'ALTER TABLE "solver_diagnostic_events" NO FORCE ROW LEVEL SECURITY'
        )
        op.execute(
            'ALTER TABLE "solver_diagnostic_events" DISABLE ROW LEVEL SECURITY'
        )

    op.drop_index(
        "ix_solver_diagnostics_employee_id",
        table_name="solver_diagnostic_events",
    )
    op.drop_index(
        "ix_solver_diagnostics_role_id",
        table_name="solver_diagnostic_events",
    )
    op.drop_index(
        "ix_solver_diagnostics_shift_slot_id",
        table_name="solver_diagnostic_events",
    )
    op.drop_index(
        "ix_solver_diagnostics_schedule_run_id",
        table_name="solver_diagnostic_events",
    )
    op.drop_index(
        "ix_solver_diagnostics_organization_id",
        table_name="solver_diagnostic_events",
    )
    op.drop_table("solver_diagnostic_events")
