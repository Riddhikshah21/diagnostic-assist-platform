"""Prepare a diagnostic result for a consistent session revision."""

from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.engine import Engine

from diagnostic_assist.diagnosis_service import (
    DiagnosticResult,
    prepare_diagnostic_result,
)
from diagnostic_assist.ollama_client import OllamaClient
from diagnostic_assist.session_retrieval import (
    SessionChangedError,
    retrieve_session_evidence,
)
from diagnostic_assist.sessions import get_session


class SessionDiagnosticResponse(BaseModel):
    session_id: UUID
    revision: int = Field(ge=1)
    result: DiagnosticResult


def prepare_session_diagnosis(
    engine: Engine,
    embedder,
    client: OllamaClient,
    organisation_id: str,
    session_id: UUID,
) -> SessionDiagnosticResponse:
    session = get_session(engine, organisation_id, session_id)

    retrieved = retrieve_session_evidence(
        engine,
        embedder,
        organisation_id,
        session_id,
    )

    if retrieved.revision != session.revision:
        raise SessionChangedError(
            "The session changed before diagnostic generation."
        )

    asked_questions = [
        observation.question
        for observation in session.observations
        if observation.question
    ]

    result = prepare_diagnostic_result(
        retrieved.evidence,
        client,
        asked_questions=asked_questions,
    )

    current = get_session(engine, organisation_id, session_id)

    if current.revision != session.revision:
        raise SessionChangedError(
            "The session changed during diagnostic generation."
        )

    return SessionDiagnosticResponse(
        session_id=session.session_id,
        revision=session.revision,
        result=result,
    )