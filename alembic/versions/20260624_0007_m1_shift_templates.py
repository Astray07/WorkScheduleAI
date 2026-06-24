"""create m1 shift templates

Revision ID: 20260624_0007
Revises: 20260624_0006
Create Date: 2026-06-24 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260624_0007"
down_revision: str | None = "20260624_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "shift_types",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("local_start_time", sa.Text(), nullable=False),
        sa.Column("local_end_time", sa.Text(), nullable=False),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column("crosses_midnight", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "local_start_time <> local_end_time",
            name="ck_shift_types_time_not_equal",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_shift_types_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_shift_types"),
        sa.UniqueConstraint(
            "organization_id",
            "name",
            name="uq_shift_types_organization_name",
        ),
    )
    op.create_index(
        "ix_shift_types_organization_id",
        "shift_types",
        ["organization_id"],
        unique=False,
    )

    op.create_table(
        "shift_requirements",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("shift_type_id", sa.Text(), nullable=False),
        sa.Column("role_id", sa.Text(), nullable=False),
        sa.Column("required_count", sa.Integer(), nullable=False),
        sa.Column("unfilled_weight_override", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "required_count >= 1",
            name="ck_shift_requirements_required_count",
        ),
        sa.CheckConstraint(
            "unfilled_weight_override IS NULL OR unfilled_weight_override >= 0",
            name="ck_shift_requirements_unfilled_weight_override",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_shift_requirements_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name="fk_shift_requirements_role_id_roles",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["shift_type_id"],
            ["shift_types.id"],
            name="fk_shift_requirements_shift_type_id_shift_types",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_shift_requirements"),
        sa.UniqueConstraint(
            "shift_type_id",
            "role_id",
            name="uq_shift_requirements_shift_type_role",
        ),
    )
    op.create_index(
        "ix_shift_requirements_organization_id",
        "shift_requirements",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_shift_requirements_shift_type_id",
        "shift_requirements",
        ["shift_type_id"],
        unique=False,
    )
    op.create_index(
        "ix_shift_requirements_role_id",
        "shift_requirements",
        ["role_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_shift_requirements_role_id", table_name="shift_requirements")
    op.drop_index(
        "ix_shift_requirements_shift_type_id",
        table_name="shift_requirements",
    )
    op.drop_index(
        "ix_shift_requirements_organization_id",
        table_name="shift_requirements",
    )
    op.drop_table("shift_requirements")
    op.drop_index("ix_shift_types_organization_id", table_name="shift_types")
    op.drop_table("shift_types")
