"""Local API for Diagnostic Assist."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from diagnostic_assist.database import create_database_engine
from diagnostic_assist.db_retrieval import search_hybrid_cases
from diagnostic_assist.embedding_store import MODEL_NAME
from diagnostic_assist.models import EvidenceBundle
from diagnostic_assist.retrieval import SentenceTransformerEmbedder

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