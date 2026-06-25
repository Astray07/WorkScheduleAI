"""add active weekdays to shift types

Revision ID: 20260625_0013
Revises: 20260624_0012
Create Date: 2026-06-25 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260625_0013"
down_revision: str | None = "20260624_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "shift_types",
        sa.Column(
            "active_weekdays",
            sa.Text(),
            nullable=False,
            server_default="0,1,2,3,4,5,6",
        ),
    )


def downgrade() -> None:
    op.drop_column("shift_types", "active_weekdays")
