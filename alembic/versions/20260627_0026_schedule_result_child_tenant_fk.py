"""Add tenant composite constraints for schedule result rows.

Revision ID: 20260627_0026
Revises: 20260627_0025
Create Date: 2026-06-27
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260627_0026"
down_revision: str | None = "20260627_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("shift_slots") as batch_op:
        batch_op.create_foreign_key(
            "fk_shift_slots_tenant_schedule_run",
            "schedule_runs",
            ["organization_id", "schedule_run_id"],
            ["organization_id", "id"],
            ondelete="CASCADE",
        )
    with op.batch_alter_table("schedule_requirements") as batch_op:
        batch_op.create_foreign_key(
            "fk_schedule_requirements_tenant_schedule_run",
            "schedule_runs",
            ["organization_id", "schedule_run_id"],
            ["organization_id", "id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_schedule_requirements_tenant_shift_slot",
            "shift_slots",
            ["organization_id", "shift_slot_id"],
            ["organization_id", "id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_schedule_requirements_tenant_role",
            "roles",
            ["organization_id", "role_id"],
            ["organization_id", "id"],
            ondelete="CASCADE",
        )
    with op.batch_alter_table("schedule_issues") as batch_op:
        batch_op.create_foreign_key(
            "fk_schedule_issues_tenant_schedule_run",
            "schedule_runs",
            ["organization_id", "schedule_run_id"],
            ["organization_id", "id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_schedule_issues_tenant_shift_slot",
            "shift_slots",
            ["organization_id", "shift_slot_id"],
            ["organization_id", "id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_schedule_issues_tenant_role",
            "roles",
            ["organization_id", "role_id"],
            ["organization_id", "id"],
            ondelete="CASCADE",
        )
    with op.batch_alter_table("relaxation_proposals") as batch_op:
        batch_op.create_foreign_key(
            "fk_relaxation_proposals_tenant_schedule_run",
            "schedule_runs",
            ["organization_id", "schedule_run_id"],
            ["organization_id", "id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_relaxation_proposals_tenant_shift_slot",
            "shift_slots",
            ["organization_id", "affected_shift_slot_id"],
            ["organization_id", "id"],
            ondelete="CASCADE",
        )
    with op.batch_alter_table("solver_diagnostic_events") as batch_op:
        batch_op.create_foreign_key(
            "fk_solver_diagnostics_tenant_schedule_run",
            "schedule_runs",
            ["organization_id", "schedule_run_id"],
            ["organization_id", "id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_solver_diagnostics_tenant_shift_slot",
            "shift_slots",
            ["organization_id", "shift_slot_id"],
            ["organization_id", "id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_solver_diagnostics_tenant_role",
            "roles",
            ["organization_id", "role_id"],
            ["organization_id", "id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_solver_diagnostics_tenant_employee",
            "employees",
            ["organization_id", "employee_id"],
            ["organization_id", "id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    with op.batch_alter_table("solver_diagnostic_events") as batch_op:
        batch_op.drop_constraint(
            "fk_solver_diagnostics_tenant_employee",
            type_="foreignkey",
        )
        batch_op.drop_constraint("fk_solver_diagnostics_tenant_role", type_="foreignkey")
        batch_op.drop_constraint(
            "fk_solver_diagnostics_tenant_shift_slot",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_solver_diagnostics_tenant_schedule_run",
            type_="foreignkey",
        )
    with op.batch_alter_table("relaxation_proposals") as batch_op:
        batch_op.drop_constraint(
            "fk_relaxation_proposals_tenant_shift_slot",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_relaxation_proposals_tenant_schedule_run",
            type_="foreignkey",
        )
    with op.batch_alter_table("schedule_issues") as batch_op:
        batch_op.drop_constraint("fk_schedule_issues_tenant_role", type_="foreignkey")
        batch_op.drop_constraint(
            "fk_schedule_issues_tenant_shift_slot",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_schedule_issues_tenant_schedule_run",
            type_="foreignkey",
        )
    with op.batch_alter_table("schedule_requirements") as batch_op:
        batch_op.drop_constraint(
            "fk_schedule_requirements_tenant_role",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_schedule_requirements_tenant_shift_slot",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_schedule_requirements_tenant_schedule_run",
            type_="foreignkey",
        )
    with op.batch_alter_table("shift_slots") as batch_op:
        batch_op.drop_constraint(
            "fk_shift_slots_tenant_schedule_run",
            type_="foreignkey",
        )
