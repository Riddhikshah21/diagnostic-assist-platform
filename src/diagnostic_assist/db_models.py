"""Database tables for persisted application data."""

from datetime import datetime
from pgvector.sqlalchemy import VECTOR
from sqlalchemy import DateTime, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Computed
from sqlalchemy.dialects.postgresql import TSVECTOR
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKeyConstraint,
    Integer,
    Uuid,
)
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

class DiagnosticSessionRecord(Base):
    __tablename__ = "diagnostic_sessions"

    organisation_id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
    )
    session_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    equipment_type: Mapped[str] = mapped_column(String)
    initial_description: Mapped[str] = mapped_column(Text)

    status: Mapped[str] = mapped_column(
        String,
        server_default=text("'active'"),
        nullable=False,
    )

    revision: Mapped[int] = mapped_column(
        Integer,
        server_default=text("1"),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'completed')",
            name="ck_diagnostic_sessions_status",
        ),
        CheckConstraint(
            "revision > 0",
            name="ck_diagnostic_sessions_revision",
        ),
        Index(
            "ix_diagnostic_sessions_org_created",
            "organisation_id",
            "created_at",
        ),
    )


class SessionObservationRecord(Base):
    __tablename__ = "session_observations"

    observation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    organisation_id: Mapped[str] = mapped_column(String)
    session_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True))

    question: Mapped[str | None] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text)

    is_unknown: Mapped[bool] = mapped_column(
        Boolean,
        server_default=text("false"),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["organisation_id", "session_id"],
            [
                "diagnostic_sessions.organisation_id",
                "diagnostic_sessions.session_id",
            ],
            name="fk_session_observations_session",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "(is_unknown AND answer IS NULL) OR "
            "(NOT is_unknown AND answer IS NOT NULL "
            "AND length(btrim(answer)) > 0)",
            name="ck_session_observations_answer",
        ),
        Index(
            "ix_session_observations_session_created",
            "organisation_id",
            "session_id",
            "created_at",
        ),
    )