"""Add tenant composite constraints for assignments.

Revision ID: 20260627_0024
Revises: 20260627_0023
Create Date: 2026-06-27
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260627_0024"
down_revision: str | None = "20260627_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("schedule_runs") as batch_op:
        batch_op.create_unique_constraint(
            "uq_schedule_runs_organization_id",
            ["organization_id", "id"],
        )
    with op.batch_alter_table("shift_slots") as batch_op:
        batch_op.create_unique_constraint(
            "uq_shift_slots_organization_id",
            ["organization_id", "id"],
        )
    with op.batch_alter_table("assignments") as batch_op:
        batch_op.create_foreign_key(
            "fk_assignments_tenant_schedule_run",
            "schedule_runs",
            ["organization_id", "schedule_run_id"],
            ["organization_id", "id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_assignments_tenant_shift_slot",
            "shift_slots",
            ["organization_id", "shift_slot_id"],
            ["organization_id", "id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_assignments_tenant_role",
            "roles",
            ["organization_id", "role_id"],
            ["organization_id", "id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_assignments_tenant_employee",
            "employees",
            ["organization_id", "employee_id"],
            ["organization_id", "id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    with op.batch_alter_table("assignments") as batch_op:
        batch_op.drop_constraint(
            "fk_assignments_tenant_employee",
            type_="foreignkey",
        )
        batch_op.drop_constraint("fk_assignments_tenant_role", type_="foreignkey")
        batch_op.drop_constraint(
            "fk_assignments_tenant_shift_slot",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_assignments_tenant_schedule_run",
            type_="foreignkey",
        )
    with op.batch_alter_table("shift_slots") as batch_op:
        batch_op.drop_constraint("uq_shift_slots_organization_id", type_="unique")
    with op.batch_alter_table("schedule_runs") as batch_op:
        batch_op.drop_constraint("uq_schedule_runs_organization_id", type_="unique")

