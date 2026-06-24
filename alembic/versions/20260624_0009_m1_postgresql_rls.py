"""create m1 postgresql tenant rls policies

Revision ID: 20260624_0009
Revises: 20260624_0008
Create Date: 2026-06-24 00:00:00
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260624_0009"
down_revision: str | None = "20260624_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TENANT_TABLES = [
    "memberships",
    "employees",
    "roles",
    "employee_roles",
    "pair_constraints",
    "unavailabilities",
    "schedule_runs",
    "schedule_input_snapshots",
    "override_approvals",
    "schedule_recalculation_requests",
    "schedule_publications",
    "shift_types",
    "shift_requirements",
    "shift_slots",
    "schedule_requirements",
    "assignments",
    "schedule_issues",
    "relaxation_proposals",
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for table_name in TENANT_TABLES:
        quoted_table = f'"{table_name}"'
        op.execute(f"ALTER TABLE {quoted_table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {quoted_table} FORCE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {quoted_table}")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {quoted_table}
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
    if bind.dialect.name != "postgresql":
        return

    for table_name in reversed(TENANT_TABLES):
        quoted_table = f'"{table_name}"'
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {quoted_table}")
        op.execute(f"ALTER TABLE {quoted_table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {quoted_table} DISABLE ROW LEVEL SECURITY")
