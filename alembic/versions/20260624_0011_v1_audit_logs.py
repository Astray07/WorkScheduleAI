"""create v1 audit logs

Revision ID: 20260624_0011
Revises: 20260624_0010
Create Date: 2026-06-24 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260624_0011"
down_revision: str | None = "20260624_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("actor_user_id", sa.Text(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("target_id", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_audit_logs_organization_id",
        "audit_logs",
        ["organization_id"],
    )
    op.create_index(
        "ix_audit_logs_target",
        "audit_logs",
        ["target_type", "target_id"],
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute('ALTER TABLE "audit_logs" ENABLE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE "audit_logs" FORCE ROW LEVEL SECURITY')
        op.execute(
            """
            CREATE POLICY tenant_isolation ON "audit_logs"
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
    if bind.dialect.name == "postgresql":
        op.execute('DROP POLICY IF EXISTS tenant_isolation ON "audit_logs"')
        op.execute('ALTER TABLE "audit_logs" NO FORCE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE "audit_logs" DISABLE ROW LEVEL SECURITY')

    op.drop_index("ix_audit_logs_target", table_name="audit_logs")
    op.drop_index("ix_audit_logs_organization_id", table_name="audit_logs")
    op.drop_table("audit_logs")
