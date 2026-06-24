"""create m1 unavailabilities

Revision ID: 20260624_0002
Revises: 20260624_0001
Create Date: 2026-06-24 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260624_0002"
down_revision: str | None = "20260624_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "unavailabilities",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("employee_id", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("override_allowed", sa.Boolean(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "type IN ('vacation', 'business_trip', 'training', 'personal')",
            name="ck_unavailabilities_type",
        ),
        sa.CheckConstraint(
            "starts_at < ends_at",
            name="ck_unavailabilities_time_order",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            name="fk_unavailabilities_employee_id_employees",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_unavailabilities_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_unavailabilities"),
    )
    op.create_index(
        "ix_unavailabilities_organization_id",
        "unavailabilities",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_unavailabilities_employee_id",
        "unavailabilities",
        ["employee_id"],
        unique=False,
    )
    op.create_index(
        "ix_unavailabilities_employee_time",
        "unavailabilities",
        ["employee_id", "starts_at", "ends_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_unavailabilities_employee_time", table_name="unavailabilities")
    op.drop_index("ix_unavailabilities_employee_id", table_name="unavailabilities")
    op.drop_index(
        "ix_unavailabilities_organization_id",
        table_name="unavailabilities",
    )
    op.drop_table("unavailabilities")
