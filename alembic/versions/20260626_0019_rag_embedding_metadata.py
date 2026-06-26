"""Add RAG embedding metadata fields.

Revision ID: 20260626_0019
Revises: 20260626_0018
Create Date: 2026-06-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260626_0019"
down_revision: str | None = "20260626_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("rag_document_chunks") as batch_op:
        batch_op.add_column(sa.Column("embedding_model", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("embedding_dimensions", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("embedding_vector_json", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("embedding_content_hash", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("rag_document_chunks") as batch_op:
        batch_op.drop_column("embedding_content_hash")
        batch_op.drop_column("embedding_vector_json")
        batch_op.drop_column("embedding_dimensions")
        batch_op.drop_column("embedding_model")
