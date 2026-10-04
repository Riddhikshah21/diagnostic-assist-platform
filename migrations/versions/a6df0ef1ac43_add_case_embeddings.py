"""Add case embeddings

Revision ID: a6df0ef1ac43
Revises: ae2f331c0d0a
Create Date: 2026-10-03 22:43:35.907043

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import VECTOR


# revision identifiers, used by Alembic.
revision: str = 'a6df0ef1ac43'
down_revision: Union[str, None] = 'ae2f331c0d0a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.add_column(
        "historical_cases",
        sa.Column("embedding", VECTOR(384), nullable=True),
    )
    op.add_column(
        "historical_cases",
        sa.Column("embedding_model", sa.Text(), nullable=True),
    )
    op.add_column(
        "historical_cases",
        sa.Column("embedding_text_hash", sa.String(64), nullable=True),
    )
    op.add_column(
        "historical_cases",
        sa.Column(
            "embedding_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("historical_cases", "embedding_updated_at")
    op.drop_column("historical_cases", "embedding_text_hash")
    op.drop_column("historical_cases", "embedding_model")
    op.drop_column("historical_cases", "embedding")
