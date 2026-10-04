"""Database tables for persisted application data."""

from datetime import datetime
from pgvector.sqlalchemy import VECTOR
from sqlalchemy import DateTime, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Computed
from sqlalchemy.dialects.postgresql import TSVECTOR

class Base(DeclarativeBase):
    pass


class HistoricalCaseRecord(Base):
    embedding: Mapped[list[float] | None] = mapped_column(
        VECTOR(384),
        nullable=True,
    )

    embedding_model: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    embedding_text_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    embedding_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    __tablename__ = "historical_cases"

    # Case IDs are unique within an organisation.
    organisation_id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
    )
    case_id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
    )

    equipment_family: Mapped[str] = mapped_column(String)
    equipment_type: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True)
    )
    language: Mapped[str] = mapped_column(String)

    customer_description: Mapped[str] = mapped_column(Text)
    technician_notes: Mapped[str | None] = mapped_column(Text)
    resolution_text: Mapped[str | None] = mapped_column(Text)

    parts_replaced: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        server_default=text("'[]'::jsonb"),
    )

    stored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    search_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''"),
    )

    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('simple'::regconfig, search_text)",
            persisted=True,
        ),
        nullable=False,
    )
    __table_args__ = (
        Index(
            "ix_historical_cases_org_type",
            "organisation_id",
            "equipment_type",
        ),
        Index(
            "ix_historical_cases_org_family",
            "organisation_id",
            "equipment_family",
        ),
        Index(
            "ix_historical_cases_search_vector",
            "search_vector",
            postgresql_using="gin",
        ),
    )