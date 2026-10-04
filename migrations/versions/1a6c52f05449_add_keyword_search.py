"""Add keyword search

Revision ID: 1a6c52f05449
Revises: a6df0ef1ac43
Create Date: 2026-10-03 22:58:18.150139

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '1a6c52f05449'
down_revision: Union[str, None] = 'a6df0ef1ac43'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "historical_cases",
        sa.Column(
            "search_text",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
    )

    op.add_column(
        "historical_cases",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('simple'::regconfig, search_text)",
                persisted=True,
            ),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_historical_cases_search_vector",
        "historical_cases",
        ["search_vector"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_historical_cases_search_vector",
        table_name="historical_cases",
    )
    op.drop_column("historical_cases", "search_vector")
    op.drop_column("historical_cases", "search_text")