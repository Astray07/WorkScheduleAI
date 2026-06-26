"""Add tenant composite constraint for unavailabilities.

Revision ID: 20260626_0021
Revises: 20260626_0020
Create Date: 2026-06-26
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260626_0021"
down_revision: str | None = "20260626_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("unavailabilities") as batch_op:
        batch_op.create_foreign_key(
            "fk_unavailabilities_tenant_employee",
            "employees",
            ["organization_id", "employee_id"],
            ["organization_id", "id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    with op.batch_alter_table("unavailabilities") as batch_op:
        batch_op.drop_constraint(
            "fk_unavailabilities_tenant_employee",
            type_="foreignkey",
        )
