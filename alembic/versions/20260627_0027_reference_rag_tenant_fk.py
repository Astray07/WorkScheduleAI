"""Add tenant composite constraints for reference and RAG rows.

Revision ID: 20260627_0027
Revises: 20260627_0026
Create Date: 2026-06-27
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260627_0027"
down_revision: str | None = "20260627_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("shift_types") as batch_op:
        batch_op.create_unique_constraint(
            "uq_shift_types_organization_id",
            ["organization_id", "id"],
        )
    with op.batch_alter_table("rag_documents") as batch_op:
        batch_op.create_unique_constraint(
            "uq_rag_documents_organization_id",
            ["organization_id", "id"],
        )
    with op.batch_alter_table("shift_requirements") as batch_op:
        batch_op.create_foreign_key(
            "fk_shift_requirements_tenant_shift_type",
            "shift_types",
            ["organization_id", "shift_type_id"],
            ["organization_id", "id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_shift_requirements_tenant_role",
            "roles",
            ["organization_id", "role_id"],
            ["organization_id", "id"],
            ondelete="CASCADE",
        )
    with op.batch_alter_table("pair_constraints") as batch_op:
        batch_op.create_foreign_key(
            "fk_pair_constraints_tenant_employee_a",
            "employees",
            ["organization_id", "employee_a_id"],
            ["organization_id", "id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_pair_constraints_tenant_employee_b",
            "employees",
            ["organization_id", "employee_b_id"],
            ["organization_id", "id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_pair_constraints_tenant_normalized_employee_a",
            "employees",
            ["organization_id", "normalized_employee_a_id"],
            ["organization_id", "id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_pair_constraints_tenant_normalized_employee_b",
            "employees",
            ["organization_id", "normalized_employee_b_id"],
            ["organization_id", "id"],
            ondelete="CASCADE",
        )
    with op.batch_alter_table("compliance_warning_overrides") as batch_op:
        batch_op.create_foreign_key(
            "fk_compliance_warning_overrides_tenant_schedule_run",
            "schedule_runs",
            ["organization_id", "schedule_run_id"],
            ["organization_id", "id"],
            ondelete="CASCADE",
        )
    with op.batch_alter_table("rag_document_chunks") as batch_op:
        batch_op.create_foreign_key(
            "fk_rag_document_chunks_tenant_document",
            "rag_documents",
            ["organization_id", "document_id"],
            ["organization_id", "id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    with op.batch_alter_table("rag_document_chunks") as batch_op:
        batch_op.drop_constraint(
            "fk_rag_document_chunks_tenant_document",
            type_="foreignkey",
        )
    with op.batch_alter_table("compliance_warning_overrides") as batch_op:
        batch_op.drop_constraint(
            "fk_compliance_warning_overrides_tenant_schedule_run",
            type_="foreignkey",
        )
    with op.batch_alter_table("pair_constraints") as batch_op:
        batch_op.drop_constraint(
            "fk_pair_constraints_tenant_normalized_employee_b",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_pair_constraints_tenant_normalized_employee_a",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_pair_constraints_tenant_employee_b",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_pair_constraints_tenant_employee_a",
            type_="foreignkey",
        )
    with op.batch_alter_table("shift_requirements") as batch_op:
        batch_op.drop_constraint(
            "fk_shift_requirements_tenant_role",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_shift_requirements_tenant_shift_type",
            type_="foreignkey",
        )
    with op.batch_alter_table("rag_documents") as batch_op:
        batch_op.drop_constraint("uq_rag_documents_organization_id", type_="unique")
    with op.batch_alter_table("shift_types") as batch_op:
        batch_op.drop_constraint("uq_shift_types_organization_id", type_="unique")
