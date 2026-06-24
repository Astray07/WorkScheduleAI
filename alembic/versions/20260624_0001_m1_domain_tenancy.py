"""create m1 domain tenancy foundation

Revision ID: 20260624_0001
Revises:
Create Date: 2026-06-24 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260624_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column("data_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_organizations"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_table(
        "employees",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("employee_code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("seniority_level", sa.Integer(), nullable=True),
        sa.Column("max_shifts_per_week", sa.Integer(), nullable=True),
        sa.Column("max_shifts_per_month", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_employees_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_employees"),
        sa.UniqueConstraint(
            "organization_id",
            "employee_code",
            name="uq_employees_organization_employee_code",
        ),
    )
    op.create_index(
        "ix_employees_organization_id",
        "employees",
        ["organization_id"],
        unique=False,
    )
    op.create_table(
        "memberships",
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "role IN ('admin', 'member')",
            name="ck_memberships_role",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_memberships_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_memberships_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "user_id",
            name="pk_memberships",
        ),
    )
    op.create_table(
        "roles",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_roles_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_roles"),
        sa.UniqueConstraint(
            "organization_id",
            "name",
            name="uq_roles_organization_name",
        ),
    )
    op.create_index(
        "ix_roles_organization_id",
        "roles",
        ["organization_id"],
        unique=False,
    )
    op.create_table(
        "employee_roles",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("employee_id", sa.Text(), nullable=False),
        sa.Column("role_id", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            name="fk_employee_roles_employee_id_employees",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_employee_roles_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name="fk_employee_roles_role_id_roles",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_employee_roles"),
        sa.UniqueConstraint(
            "organization_id",
            "employee_id",
            "role_id",
            name="uq_employee_roles_organization_employee_role",
        ),
    )
    op.create_index(
        "ix_employee_roles_employee_id",
        "employee_roles",
        ["employee_id"],
        unique=False,
    )
    op.create_index(
        "ix_employee_roles_organization_id",
        "employee_roles",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_employee_roles_role_id",
        "employee_roles",
        ["role_id"],
        unique=False,
    )
    op.create_table(
        "pair_constraints",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("employee_a_id", sa.Text(), nullable=False),
        sa.Column("employee_b_id", sa.Text(), nullable=False),
        sa.Column("normalized_employee_a_id", sa.Text(), nullable=False),
        sa.Column("normalized_employee_b_id", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("override_allowed", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "normalized_employee_a_id < normalized_employee_b_id",
            name="ck_pair_constraints_normalized_order",
        ),
        sa.CheckConstraint(
            "type IN ('blocked', 'avoid', 'prefer')",
            name="ck_pair_constraints_type",
        ),
        sa.CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_pair_constraints_severity",
        ),
        sa.ForeignKeyConstraint(
            ["employee_a_id"],
            ["employees.id"],
            name="fk_pair_constraints_employee_a_id_employees",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["employee_b_id"],
            ["employees.id"],
            name="fk_pair_constraints_employee_b_id_employees",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["normalized_employee_a_id"],
            ["employees.id"],
            name="fk_pair_constraints_normalized_employee_a_id_employees",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["normalized_employee_b_id"],
            ["employees.id"],
            name="fk_pair_constraints_normalized_employee_b_id_employees",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_pair_constraints_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pair_constraints"),
        sa.UniqueConstraint(
            "organization_id",
            "normalized_employee_a_id",
            "normalized_employee_b_id",
            "type",
            name="uq_pair_constraints_normalized_pair_type",
        ),
    )
    op.create_index(
        "ix_pair_constraints_normalized_employee_a_id",
        "pair_constraints",
        ["normalized_employee_a_id"],
        unique=False,
    )
    op.create_index(
        "ix_pair_constraints_normalized_employee_b_id",
        "pair_constraints",
        ["normalized_employee_b_id"],
        unique=False,
    )
    op.create_index(
        "ix_pair_constraints_organization_id",
        "pair_constraints",
        ["organization_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pair_constraints_organization_id",
        table_name="pair_constraints",
    )
    op.drop_index(
        "ix_pair_constraints_normalized_employee_b_id",
        table_name="pair_constraints",
    )
    op.drop_index(
        "ix_pair_constraints_normalized_employee_a_id",
        table_name="pair_constraints",
    )
    op.drop_table("pair_constraints")
    op.drop_index("ix_employee_roles_role_id", table_name="employee_roles")
    op.drop_index("ix_employee_roles_organization_id", table_name="employee_roles")
    op.drop_index("ix_employee_roles_employee_id", table_name="employee_roles")
    op.drop_table("employee_roles")
    op.drop_index("ix_roles_organization_id", table_name="roles")
    op.drop_table("roles")
    op.drop_table("memberships")
    op.drop_index("ix_employees_organization_id", table_name="employees")
    op.drop_table("employees")
    op.drop_table("users")
    op.drop_table("organizations")

