"""Add tenant composite constraint for employee requests.

Revision ID: 20260627_0023
Revises: 20260626_0022
Create Date: 2026-06-27
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260627_0023"
down_revision: str | None = "20260626_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("employee_requests") as batch_op:
        batch_op.create_foreign_key(
            "fk_employee_requests_tenant_employee",
            "employees",
            ["organization_id", "employee_id"],
            ["organization_id", "id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    with op.batch_alter_table("employee_requests") as batch_op:
        batch_op.drop_constraint(
            "fk_employee_requests_tenant_employee",
            type_="foreignkey",
        )
