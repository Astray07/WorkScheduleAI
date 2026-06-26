"""Add tenant composite constraints for employee roles.

Revision ID: 20260626_0020
Revises: 20260626_0019
Create Date: 2026-06-26
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260626_0020"
down_revision: str | None = "20260626_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("employees") as batch_op:
        batch_op.create_unique_constraint(
            "uq_employees_organization_id",
            ["organization_id", "id"],
        )
    with op.batch_alter_table("roles") as batch_op:
        batch_op.create_unique_constraint(
            "uq_roles_organization_id",
            ["organization_id", "id"],
        )
    with op.batch_alter_table("employee_roles") as batch_op:
        batch_op.create_foreign_key(
            "fk_employee_roles_tenant_employee",
            "employees",
            ["organization_id", "employee_id"],
            ["organization_id", "id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_employee_roles_tenant_role",
            "roles",
            ["organization_id", "role_id"],
            ["organization_id", "id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    with op.batch_alter_table("employee_roles") as batch_op:
        batch_op.drop_constraint("fk_employee_roles_tenant_role", type_="foreignkey")
        batch_op.drop_constraint("fk_employee_roles_tenant_employee", type_="foreignkey")
    with op.batch_alter_table("roles") as batch_op:
        batch_op.drop_constraint("uq_roles_organization_id", type_="unique")
    with op.batch_alter_table("employees") as batch_op:
        batch_op.drop_constraint("uq_employees_organization_id", type_="unique")
