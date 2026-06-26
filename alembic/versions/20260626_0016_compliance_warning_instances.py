"""Store compliance warning overrides by warning instance.

Revision ID: 20260626_0016
Revises: 20260626_0015
Create Date: 2026-06-26
"""

from alembic import op
import sqlalchemy as sa


revision = "20260626_0016"
down_revision = "20260626_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("compliance_warning_overrides") as batch_op:
        batch_op.add_column(
            sa.Column(
                "employee_id",
                sa.Text(),
                nullable=False,
                server_default="",
            )
        )
        batch_op.add_column(
            sa.Column("slot_id", sa.Text(), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column("week_key", sa.Text(), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column(
                "snapshot_hash",
                sa.Text(),
                nullable=False,
                server_default="",
            )
        )
        batch_op.drop_constraint(
            "uq_compliance_warning_overrides_run_code",
            type_="unique",
        )
        batch_op.create_unique_constraint(
            "uq_compliance_warning_overrides_instance",
            [
                "organization_id",
                "schedule_run_id",
                "warning_code",
                "employee_id",
                "slot_id",
                "week_key",
                "snapshot_hash",
            ],
        )
    with op.batch_alter_table("compliance_warning_overrides") as batch_op:
        batch_op.alter_column(
            "employee_id",
            existing_type=sa.Text(),
            server_default=None,
        )
        batch_op.alter_column(
            "slot_id",
            existing_type=sa.Text(),
            server_default=None,
        )
        batch_op.alter_column(
            "week_key",
            existing_type=sa.Text(),
            server_default=None,
        )
        batch_op.alter_column(
            "snapshot_hash",
            existing_type=sa.Text(),
            server_default=None,
        )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            """
            DELETE FROM compliance_warning_overrides
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM compliance_warning_overrides
                GROUP BY organization_id, schedule_run_id, warning_code
            )
            """
        )
    )
    with op.batch_alter_table("compliance_warning_overrides") as batch_op:
        batch_op.drop_constraint(
            "uq_compliance_warning_overrides_instance",
            type_="unique",
        )
        batch_op.create_unique_constraint(
            "uq_compliance_warning_overrides_run_code",
            ["organization_id", "schedule_run_id", "warning_code"],
        )
        batch_op.drop_column("snapshot_hash")
        batch_op.drop_column("week_key")
        batch_op.drop_column("slot_id")
        batch_op.drop_column("employee_id")
