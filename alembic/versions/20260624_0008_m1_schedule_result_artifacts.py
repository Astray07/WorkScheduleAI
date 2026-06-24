"""create m1 schedule result artifacts

Revision ID: 20260624_0008
Revises: 20260624_0007
Create Date: 2026-06-24 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260624_0008"
down_revision: str | None = "20260624_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "shift_slots",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("schedule_run_id", sa.Text(), nullable=False),
        sa.Column("shift_type_id", sa.Text(), nullable=True),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("starts_at", sa.Text(), nullable=False),
        sa.Column("ends_at", sa.Text(), nullable=False),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["schedule_run_id"], ["schedule_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shift_type_id"], ["shift_types.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shift_slots_organization_id", "shift_slots", ["organization_id"])
    op.create_index("ix_shift_slots_schedule_run_id", "shift_slots", ["schedule_run_id"])

    op.create_table(
        "schedule_requirements",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("schedule_run_id", sa.Text(), nullable=False),
        sa.Column("shift_slot_id", sa.Text(), nullable=False),
        sa.Column("role_id", sa.Text(), nullable=False),
        sa.Column("role_name", sa.Text(), nullable=False),
        sa.Column("required_count", sa.Integer(), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["schedule_run_id"], ["schedule_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shift_slot_id"], ["shift_slots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_schedule_requirements_organization_id", "schedule_requirements", ["organization_id"])
    op.create_index("ix_schedule_requirements_schedule_run_id", "schedule_requirements", ["schedule_run_id"])
    op.create_index("ix_schedule_requirements_shift_slot_id", "schedule_requirements", ["shift_slot_id"])
    op.create_index("ix_schedule_requirements_role_id", "schedule_requirements", ["role_id"])

    op.create_table(
        "assignments",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("schedule_run_id", sa.Text(), nullable=False),
        sa.Column("shift_slot_id", sa.Text(), nullable=False),
        sa.Column("role_id", sa.Text(), nullable=False),
        sa.Column("employee_id", sa.Text(), nullable=False),
        sa.Column("employee_name", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("locked_by_user", sa.Boolean(), nullable=False),
        sa.Column("warning_state", sa.Text(), nullable=False),
        sa.Column("warning_message", sa.Text(), nullable=True),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["schedule_run_id"], ["schedule_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shift_slot_id"], ["shift_slots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("schedule_run_id", "shift_slot_id", "role_id", "employee_id", name="uq_assignments_run_slot_role_employee"),
        sa.UniqueConstraint("schedule_run_id", "shift_slot_id", "employee_id", name="uq_assignments_run_slot_employee"),
    )
    op.create_index("ix_assignments_organization_id", "assignments", ["organization_id"])
    op.create_index("ix_assignments_schedule_run_id", "assignments", ["schedule_run_id"])
    op.create_index("ix_assignments_shift_slot_id", "assignments", ["shift_slot_id"])
    op.create_index("ix_assignments_role_id", "assignments", ["role_id"])
    op.create_index("ix_assignments_employee_id", "assignments", ["employee_id"])

    op.create_table(
        "schedule_issues",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("schedule_run_id", sa.Text(), nullable=False),
        sa.Column("shift_slot_id", sa.Text(), nullable=True),
        sa.Column("role_id", sa.Text(), nullable=True),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("missing_count", sa.Integer(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.Text(), nullable=False),
        sa.Column("display_message", sa.Text(), nullable=False),
        sa.Column("related_proposal_ids_json", sa.Text(), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["schedule_run_id"], ["schedule_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shift_slot_id"], ["shift_slots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_schedule_issues_organization_id", "schedule_issues", ["organization_id"])
    op.create_index("ix_schedule_issues_schedule_run_id", "schedule_issues", ["schedule_run_id"])
    op.create_index("ix_schedule_issues_shift_slot_id", "schedule_issues", ["shift_slot_id"])
    op.create_index("ix_schedule_issues_role_id", "schedule_issues", ["role_id"])

    op.create_table(
        "relaxation_proposals",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("schedule_run_id", sa.Text(), nullable=False),
        sa.Column("group_id", sa.Text(), nullable=True),
        sa.Column("requires_proposal_ids_json", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("affected_shift_slot_id", sa.Text(), nullable=True),
        sa.Column("display_summary", sa.Text(), nullable=False),
        sa.Column("impact_preview_json", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["schedule_run_id"], ["schedule_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["affected_shift_slot_id"], ["shift_slots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_relaxation_proposals_organization_id", "relaxation_proposals", ["organization_id"])
    op.create_index("ix_relaxation_proposals_schedule_run_id", "relaxation_proposals", ["schedule_run_id"])
    op.create_index("ix_relaxation_proposals_affected_shift_slot_id", "relaxation_proposals", ["affected_shift_slot_id"])

    op.add_column(
        "schedule_publications",
        sa.Column("result_snapshot_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("schedule_publications", "result_snapshot_json")
    op.drop_index("ix_relaxation_proposals_affected_shift_slot_id", table_name="relaxation_proposals")
    op.drop_index("ix_relaxation_proposals_schedule_run_id", table_name="relaxation_proposals")
    op.drop_index("ix_relaxation_proposals_organization_id", table_name="relaxation_proposals")
    op.drop_table("relaxation_proposals")
    op.drop_index("ix_schedule_issues_role_id", table_name="schedule_issues")
    op.drop_index("ix_schedule_issues_shift_slot_id", table_name="schedule_issues")
    op.drop_index("ix_schedule_issues_schedule_run_id", table_name="schedule_issues")
    op.drop_index("ix_schedule_issues_organization_id", table_name="schedule_issues")
    op.drop_table("schedule_issues")
    op.drop_index("ix_assignments_employee_id", table_name="assignments")
    op.drop_index("ix_assignments_role_id", table_name="assignments")
    op.drop_index("ix_assignments_shift_slot_id", table_name="assignments")
    op.drop_index("ix_assignments_schedule_run_id", table_name="assignments")
    op.drop_index("ix_assignments_organization_id", table_name="assignments")
    op.drop_table("assignments")
    op.drop_index("ix_schedule_requirements_role_id", table_name="schedule_requirements")
    op.drop_index("ix_schedule_requirements_shift_slot_id", table_name="schedule_requirements")
    op.drop_index("ix_schedule_requirements_schedule_run_id", table_name="schedule_requirements")
    op.drop_index("ix_schedule_requirements_organization_id", table_name="schedule_requirements")
    op.drop_table("schedule_requirements")
    op.drop_index("ix_shift_slots_schedule_run_id", table_name="shift_slots")
    op.drop_index("ix_shift_slots_organization_id", table_name="shift_slots")
    op.drop_table("shift_slots")
