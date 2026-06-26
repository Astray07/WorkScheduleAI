"""Add publication notification delivery tracking.

Revision ID: 20260626_0018
Revises: 20260626_0017
Create Date: 2026-06-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260626_0018"
down_revision: str | None = "20260626_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("publication_notifications") as batch_op:
        batch_op.add_column(sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(
            sa.Column("delivery_attempts", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("last_delivery_error", sa.Text(), nullable=True))
    with op.batch_alter_table("publication_notifications") as batch_op:
        batch_op.alter_column("delivery_attempts", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("publication_notifications") as batch_op:
        batch_op.drop_column("last_delivery_error")
        batch_op.drop_column("delivery_attempts")
        batch_op.drop_column("delivered_at")
