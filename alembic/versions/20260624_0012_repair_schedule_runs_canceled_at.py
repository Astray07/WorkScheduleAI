"""repair schedule_runs canceled_at migration drift

Revision ID: 20260624_0012
Revises: 20260624_0011
Create Date: 2026-06-24 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20260624_0012"
down_revision: str | None = "20260624_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table_name = "schedule_runs"
    if _has_column(table_name, "canceled_at"):
        return

    op.add_column(
        table_name,
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    # Keep this repair revision non-destructive. Fresh databases already include
    # canceled_at in revision 20260624_0003, and drifted databases need it.
    return


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return any(
        column["name"] == column_name
        for column in inspector.get_columns(table_name)
    )
