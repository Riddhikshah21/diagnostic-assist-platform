"""Retrieve evidence from a saved diagnostic session."""

from uuid import UUID

from sqlalchemy.engine import Engine

from diagnostic_assist.db_retrieval import search_hybrid_cases
from diagnostic_assist.retrieval import Embedder
from diagnostic_assist.session_models import (
    SessionEvidenceResponse,
    SessionResponse,
)
from diagnostic_assist.sessions import get_session


class SessionChangedError(RuntimeError):
    """The session changed while evidence was being retrieved."""


def build_session_query(session: SessionResponse) -> str:
    lines = [session.initial_description]

    for observation in session.observations:
        if observation.is_unknown or observation.answer is None:
            continue

        if observation.question:
            lines.append(
                f"Question: {observation.question}\n"
                f"Customer answer: {observation.answer}"
            )
        else:
            lines.append(
                f"Additional observation: {observation.answer}"
            )

    return "\n\n".join(lines)


def retrieve_session_evidence(
    engine: Engine,
    embedder: Embedder,
    organisation_id: str,
    session_id: UUID,
    limit: int = 5,
    candidate_depth: int = 5,
) -> SessionEvidenceResponse:
    session = get_session(engine, organisation_id, session_id)

    evidence = search_hybrid_cases(
        engine=engine,
        embedder=embedder,
        query=build_session_query(session),
        organisation_id=organisation_id,
        equipment_type=session.equipment_type,
        limit=limit,
        candidate_depth=candidate_depth,
    )

    current = get_session(engine, organisation_id, session_id)

    if current.revision != session.revision:
        raise SessionChangedError(
            "Session changed during search. Refresh and retry."
        )

    return SessionEvidenceResponse(
        session_id=session.session_id,
        revision=session.revision,
        evidence=evidence,
    )