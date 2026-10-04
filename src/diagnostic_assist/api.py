"""Local API for Diagnostic Assist."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from uuid import UUID

from diagnostic_assist.session_models import SessionCreate, SessionResponse
from diagnostic_assist.sessions import (
    SessionNotFoundError,
    create_session,
    get_session,
)
from diagnostic_assist.database import create_database_engine
from diagnostic_assist.db_retrieval import search_hybrid_cases
from diagnostic_assist.embedding_store import MODEL_NAME
from diagnostic_assist.models import EvidenceBundle
from diagnostic_assist.retrieval import SentenceTransformerEmbedder
from diagnostic_assist.session_models import ObservationCreate
from diagnostic_assist.sessions import (
    SessionClosedError,
    add_observation,
)
from fastapi import Query

from diagnostic_assist.session_models import SessionEvidenceResponse
from diagnostic_assist.session_retrieval import (
    SessionChangedError,
    retrieve_session_evidence,
)

logger = logging.getLogger(__name__)


class SearchRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    query: str = Field(min_length=1)
    equipment_type: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=20)
    candidate_depth: int = Field(default=5, ge=1, le=100)
    exclude_case_ids: set[str] = Field(default_factory=set)


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = create_database_engine()

    try:
        organisation_id = os.getenv("APP_ORGANISATION_ID", "").strip()

        if not organisation_id:
            raise ValueError("APP_ORGANISATION_ID must be configured")

        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        embedder = SentenceTransformerEmbedder(MODEL_NAME)

        # Load the model before accepting requests.
        embedder.encode(["Initialize query embedding model."])

        app.state.engine = engine
        app.state.embedder = embedder
        app.state.organisation_id = organisation_id

        yield
    finally:
        engine.dispose()


app = FastAPI(
    title="Diagnostic Assist",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
def health(request: Request) -> dict[str, str]:
    try:
        with request.app.state.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Database health check failed")
        raise HTTPException(
            status_code=503,
            detail="Database unavailable.",
        ) from None

    return {"status": "ok"}


@app.post("/search", response_model=EvidenceBundle)
def search(payload: SearchRequest, request: Request) -> EvidenceBundle:
    try:
        return search_hybrid_cases(
            engine=request.app.state.engine,
            embedder=request.app.state.embedder,
            query=payload.query,
            organisation_id=request.app.state.organisation_id,
            equipment_type=payload.equipment_type,
            limit=payload.limit,
            candidate_depth=payload.candidate_depth,
            exclude_case_ids=payload.exclude_case_ids,
        )
    except SQLAlchemyError:
        logger.exception("Database search failed")
        raise HTTPException(
            status_code=503,
            detail="Database search failed.",
        ) from None

@app.post("/sessions", response_model=SessionResponse, status_code=201)
def create_diagnostic_session(
    payload: SessionCreate,
    request: Request,
) -> SessionResponse:
    try:
        return create_session(
            engine=request.app.state.engine,
            organisation_id=request.app.state.organisation_id,
            equipment_type=payload.equipment_type,
            initial_description=payload.initial_description,
        )
    except SQLAlchemyError:
        logger.exception("Session creation failed")
        raise HTTPException(
            status_code=503,
            detail="Unable to save the session.",
        ) from None


@app.get("/sessions/{session_id}", response_model=SessionResponse)
def load_diagnostic_session(
    session_id: UUID,
    request: Request,
) -> SessionResponse:
    try:
        return get_session(
            engine=request.app.state.engine,
            organisation_id=request.app.state.organisation_id,
            session_id=session_id,
        )
    except SessionNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Session not found.",
        ) from None
    except SQLAlchemyError:
        logger.exception("Session loading failed")
        raise HTTPException(
            status_code=503,
            detail="Unable to load the session.",
        ) from None

@app.post(
    "/sessions/{session_id}/observations",
    response_model=SessionResponse,
)
def record_observation(
    session_id: UUID,
    payload: ObservationCreate,
    request: Request,
) -> SessionResponse:
    try:
        return add_observation(
            engine=request.app.state.engine,
            organisation_id=request.app.state.organisation_id,
            session_id=session_id,
            payload=payload,
        )
    except SessionNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Session not found.",
        ) from None
    except SessionClosedError:
        raise HTTPException(
            status_code=409,
            detail="Session is already completed.",
        ) from None
    except SQLAlchemyError:
        logger.exception("Saving observation failed")
        raise HTTPException(
            status_code=503,
            detail="Unable to save the observation.",
        ) from None

@app.get(
    "/sessions/{session_id}/evidence",
    response_model=SessionEvidenceResponse,
)
def get_diagnostic_evidence(
    session_id: UUID,
    request: Request,
    limit: int = Query(default=5, ge=1, le=20),
    candidate_depth: int = Query(default=5, ge=1, le=100),
) -> SessionEvidenceResponse:
    try:
        return retrieve_session_evidence(
            engine=request.app.state.engine,
            embedder=request.app.state.embedder,
            organisation_id=request.app.state.organisation_id,
            session_id=session_id,
            limit=limit,
            candidate_depth=candidate_depth,
        )
    except SessionNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Session not found.",
        ) from None
    except SessionChangedError:
        raise HTTPException(
            status_code=409,
            detail="Session changed during search. Refresh and retry.",
        ) from None
    except SQLAlchemyError:
        logger.exception("Session evidence retrieval failed")
        raise HTTPException(
            status_code=503,
            detail="Unable to retrieve session evidence.",
        ) from None