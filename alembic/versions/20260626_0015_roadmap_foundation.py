"""create roadmap foundation tables

Revision ID: 20260626_0015
Revises: 20260625_0014
Create Date: 2026-06-26 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260626_0015"
down_revision: str | None = "20260625_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TENANT_TABLES = [
    "employee_user_links",
    "employee_requests",
    "publication_acknowledgements",
    "publication_notifications",
    "compliance_warning_overrides",
    "rag_documents",
    "rag_document_chunks",
    "rag_query_audits",
    "demand_drivers",
    "labor_budgets",
]


def upgrade() -> None:
    with op.batch_alter_table("memberships") as batch_op:
        batch_op.drop_constraint("ck_memberships_role", type_="check")
        batch_op.create_check_constraint(
            "ck_memberships_role",
            "role IN ('owner', 'admin', 'scheduler', 'viewer', 'employee', 'member')",
        )

    op.create_table(
        "employee_user_links",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("employee_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('invited', 'linked', 'disabled')",
            name="ck_employee_user_links_status",
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "employee_id",
            name="uq_employee_user_links_organization_employee",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_employee_user_links_organization_user",
        ),
    )
    op.create_index("ix_employee_user_links_organization_id", "employee_user_links", ["organization_id"])
    op.create_index("ix_employee_user_links_employee_id", "employee_user_links", ["employee_id"])
    op.create_index("ix_employee_user_links_user_id", "employee_user_links", ["user_id"])

    op.create_table(
        "employee_requests",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("employee_id", sa.Text(), nullable=False),
        sa.Column("requested_by_user_id", sa.Text(), nullable=True),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("manager_reason", sa.Text(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_unavailability_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "type IN ('vacation', 'unavailable', 'prefer_shift', 'avoid_shift', 'swap', 'open_shift')",
            name="ck_employee_requests_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'canceled')",
            name="ck_employee_requests_status",
        ),
        sa.CheckConstraint("starts_at < ends_at", name="ck_employee_requests_time_order"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["source_unavailability_id"],
            ["unavailabilities.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_employee_requests_organization_id", "employee_requests", ["organization_id"])
    op.create_index("ix_employee_requests_employee_id", "employee_requests", ["employee_id"])

    op.create_table(
        "publication_acknowledgements",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("publication_id", sa.Text(), nullable=False),
        sa.Column("employee_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'acknowledged')",
            name="ck_publication_acknowledgements_status",
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["publication_id"],
            ["schedule_publications.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "publication_id",
            "employee_id",
            name="uq_publication_acknowledgements_employee",
        ),
    )
    op.create_index(
        "ix_publication_acknowledgements_organization_id",
        "publication_acknowledgements",
        ["organization_id"],
    )
    op.create_index(
        "ix_publication_acknowledgements_publication_id",
        "publication_acknowledgements",
        ["publication_id"],
    )
    op.create_index(
        "ix_publication_acknowledgements_employee_id",
        "publication_acknowledgements",
        ["employee_id"],
    )

    op.create_table(
        "publication_notifications",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("publication_id", sa.Text(), nullable=False),
        sa.Column("employee_id", sa.Text(), nullable=False),
        sa.Column("notification_type", sa.Text(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "notification_type IN ('published', 'changed')",
            name="ck_publication_notifications_type",
        ),
        sa.CheckConstraint(
            "channel IN ('in_app', 'email', 'slack')",
            name="ck_publication_notifications_channel",
        ),
        sa.CheckConstraint(
            "status IN ('pending_recorded', 'sent', 'failed', 'suppressed')",
            name="ck_publication_notifications_status",
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["publication_id"],
            ["schedule_publications.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_publication_notifications_organization_id", "publication_notifications", ["organization_id"])
    op.create_index("ix_publication_notifications_publication_id", "publication_notifications", ["publication_id"])
    op.create_index("ix_publication_notifications_employee_id", "publication_notifications", ["employee_id"])

    op.create_table(
        "compliance_warning_overrides",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("schedule_run_id", sa.Text(), nullable=False),
        sa.Column("warning_code", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["schedule_run_id"], ["schedule_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "schedule_run_id",
            "warning_code",
            name="uq_compliance_warning_overrides_run_code",
        ),
    )
    op.create_index("ix_compliance_warning_overrides_organization_id", "compliance_warning_overrides", ["organization_id"])
    op.create_index("ix_compliance_warning_overrides_schedule_run_id", "compliance_warning_overrides", ["schedule_run_id"])

    op.create_table(
        "rag_documents",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("document_title", sa.Text(), nullable=False),
        sa.Column("checked_at", sa.Date(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rag_documents_organization_id", "rag_documents", ["organization_id"])

    op.create_table(
        "rag_document_chunks",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("document_id", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["rag_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "document_id",
            "chunk_index",
            name="uq_rag_document_chunks_document_index",
        ),
    )
    op.create_index("ix_rag_document_chunks_organization_id", "rag_document_chunks", ["organization_id"])
    op.create_index("ix_rag_document_chunks_document_id", "rag_document_chunks", ["document_id"])

    op.create_table(
        "rag_query_audits",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("query_hash", sa.Text(), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("safety_notes_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rag_query_audits_organization_id", "rag_query_audits", ["organization_id"])

    op.create_table(
        "demand_drivers",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("segment", sa.Text(), nullable=False),
        sa.Column("demand_count", sa.Integer(), nullable=False),
        sa.Column("required_staff_count", sa.Integer(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("demand_count >= 0", name="ck_demand_drivers_demand_count"),
        sa.CheckConstraint(
            "required_staff_count >= 0",
            name="ck_demand_drivers_required_staff_count",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "local_date",
            "segment",
            name="uq_demand_drivers_organization_date_segment",
        ),
    )
    op.create_index("ix_demand_drivers_organization_id", "demand_drivers", ["organization_id"])

    op.create_table(
        "labor_budgets",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("budget_amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "period_start <= period_end",
            name="ck_labor_budgets_period_order",
        ),
        sa.CheckConstraint(
            "budget_amount_cents >= 0",
            name="ck_labor_budgets_budget_amount",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_labor_budgets_organization_id", "labor_budgets", ["organization_id"])

    _enable_rls()


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table_name in reversed(TENANT_TABLES):
            quoted_table = f'"{table_name}"'
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {quoted_table}")
            op.execute(f"ALTER TABLE {quoted_table} NO FORCE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {quoted_table} DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_labor_budgets_organization_id", table_name="labor_budgets")
    op.drop_table("labor_budgets")
    op.drop_index("ix_demand_drivers_organization_id", table_name="demand_drivers")
    op.drop_table("demand_drivers")
    op.drop_index("ix_rag_query_audits_organization_id", table_name="rag_query_audits")
    op.drop_table("rag_query_audits")
    op.drop_index("ix_rag_document_chunks_document_id", table_name="rag_document_chunks")
    op.drop_index("ix_rag_document_chunks_organization_id", table_name="rag_document_chunks")
    op.drop_table("rag_document_chunks")
    op.drop_index("ix_rag_documents_organization_id", table_name="rag_documents")
    op.drop_table("rag_documents")
    op.drop_index(
        "ix_compliance_warning_overrides_schedule_run_id",
        table_name="compliance_warning_overrides",
    )
    op.drop_index(
        "ix_compliance_warning_overrides_organization_id",
        table_name="compliance_warning_overrides",
    )
    op.drop_table("compliance_warning_overrides")
    op.drop_index("ix_publication_notifications_employee_id", table_name="publication_notifications")
    op.drop_index("ix_publication_notifications_publication_id", table_name="publication_notifications")
    op.drop_index("ix_publication_notifications_organization_id", table_name="publication_notifications")
    op.drop_table("publication_notifications")
    op.drop_index(
        "ix_publication_acknowledgements_employee_id",
        table_name="publication_acknowledgements",
    )
    op.drop_index(
        "ix_publication_acknowledgements_publication_id",
        table_name="publication_acknowledgements",
    )
    op.drop_index(
        "ix_publication_acknowledgements_organization_id",
        table_name="publication_acknowledgements",
    )
    op.drop_table("publication_acknowledgements")
    op.drop_index("ix_employee_requests_employee_id", table_name="employee_requests")
    op.drop_index("ix_employee_requests_organization_id", table_name="employee_requests")
    op.drop_table("employee_requests")
    op.drop_index("ix_employee_user_links_user_id", table_name="employee_user_links")
    op.drop_index("ix_employee_user_links_employee_id", table_name="employee_user_links")
    op.drop_index("ix_employee_user_links_organization_id", table_name="employee_user_links")
    op.drop_table("employee_user_links")

    with op.batch_alter_table("memberships") as batch_op:
        batch_op.drop_constraint("ck_memberships_role", type_="check")
        batch_op.create_check_constraint(
            "ck_memberships_role",
            "role IN ('admin', 'member')",
        )


def _enable_rls() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for table_name in TENANT_TABLES:
        quoted_table = f'"{table_name}"'
        op.execute(f"ALTER TABLE {quoted_table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {quoted_table} FORCE ROW LEVEL SECURITY")
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
