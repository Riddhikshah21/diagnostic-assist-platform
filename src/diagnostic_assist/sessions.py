"""Persist and retrieve diagnostic sessions."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from diagnostic_assist.db_models import (
    DiagnosticSessionRecord,
    SessionObservationRecord,
)
from diagnostic_assist.session_models import (
    ObservationResponse,
    SessionCreate,
    SessionResponse,
    ObservationCreate,
)


class SessionNotFoundError(LookupError):
    """The session does not exist in the selected organisation."""


def create_session(
    engine: Engine,
    organisation_id: str,
    equipment_type: str,
    initial_description: str,
) -> SessionResponse:
    organisation_id = organisation_id.strip()

    if not organisation_id:
        raise ValueError("organisation_id must not be blank")

    payload = SessionCreate(
        equipment_type=equipment_type,
        initial_description=initial_description,
    )

    record = DiagnosticSessionRecord(
        organisation_id=organisation_id,
        equipment_type=payload.equipment_type,
        initial_description=payload.initial_description,
    )

    with Session(engine) as database:
        database.add(record)
        database.commit()
        database.refresh(record)

        return SessionResponse.model_validate(record)


def get_session(
    engine: Engine,
    organisation_id: str,
    session_id: UUID,
) -> SessionResponse:
    organisation_id = organisation_id.strip()

    if not organisation_id:
        raise ValueError("organisation_id must not be blank")

    with Session(engine) as database:
        record = database.scalar(
            select(DiagnosticSessionRecord)
            .where(
                DiagnosticSessionRecord.organisation_id == organisation_id,
                DiagnosticSessionRecord.session_id == session_id,
            )
            .with_for_update(read=True)
        )

        if record is None:
            raise SessionNotFoundError("Session not found.")

        observations = database.scalars(
            select(SessionObservationRecord)
            .where(
                SessionObservationRecord.organisation_id == organisation_id,
                SessionObservationRecord.session_id == session_id,
            )
            .order_by(
                SessionObservationRecord.created_at,
                SessionObservationRecord.observation_id,
            )
        ).all()

        response = SessionResponse.model_validate(record)
        response.observations = [
            ObservationResponse.model_validate(observation)
            for observation in observations
        ]

        return response

class SessionClosedError(ValueError):
    """Completed sessions cannot accept new observations."""


def add_observation(
    engine: Engine,
    organisation_id: str,
    session_id: UUID,
    payload: ObservationCreate,
) -> SessionResponse:
    organisation_id = organisation_id.strip()

    if not organisation_id:
        raise ValueError("organisation_id must not be blank")

    with Session(engine) as database:
        with database.begin():
            record = database.scalar(
                select(DiagnosticSessionRecord)
                .where(
                    DiagnosticSessionRecord.organisation_id
                    == organisation_id,
                    DiagnosticSessionRecord.session_id == session_id,
                )
                .with_for_update()
            )

            if record is None:
                raise SessionNotFoundError("Session not found.")

            if record.status != "active":
                raise SessionClosedError("Session is already completed.")

            database.add(
                SessionObservationRecord(
                    organisation_id=organisation_id,
                    session_id=session_id,
                    question=payload.question,
                    answer=payload.answer,
                    is_unknown=payload.is_unknown,
                )
            )

            record.revision += 1

    return get_session(engine, organisation_id, session_id)