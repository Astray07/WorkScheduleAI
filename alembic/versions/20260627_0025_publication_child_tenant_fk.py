"""Add tenant composite constraints for publication child rows.

Revision ID: 20260627_0025
Revises: 20260627_0024
Create Date: 2026-06-27
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260627_0025"
down_revision: str | None = "20260627_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("schedule_publications") as batch_op:
        batch_op.create_unique_constraint(
            "uq_schedule_publications_organization_id",
            ["organization_id", "id"],
        )
    with op.batch_alter_table("publication_acknowledgements") as batch_op:
        batch_op.create_foreign_key(
            "fk_publication_acknowledgements_tenant_publication",
            "schedule_publications",
            ["organization_id", "publication_id"],
            ["organization_id", "id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_publication_acknowledgements_tenant_employee",
            "employees",
            ["organization_id", "employee_id"],
            ["organization_id", "id"],
            ondelete="CASCADE",
        )
    with op.batch_alter_table("publication_notifications") as batch_op:
        batch_op.create_foreign_key(
            "fk_publication_notifications_tenant_publication",
            "schedule_publications",
            ["organization_id", "publication_id"],
            ["organization_id", "id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_publication_notifications_tenant_employee",
            "employees",
            ["organization_id", "employee_id"],
            ["organization_id", "id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    with op.batch_alter_table("publication_notifications") as batch_op:
        batch_op.drop_constraint(
            "fk_publication_notifications_tenant_employee",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_publication_notifications_tenant_publication",
            type_="foreignkey",
        )
    with op.batch_alter_table("publication_acknowledgements") as batch_op:
        batch_op.drop_constraint(
            "fk_publication_acknowledgements_tenant_employee",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_publication_acknowledgements_tenant_publication",
            type_="foreignkey",
        )
    with op.batch_alter_table("schedule_publications") as batch_op:
        batch_op.drop_constraint(
            "uq_schedule_publications_organization_id",
            type_="unique",
        )

