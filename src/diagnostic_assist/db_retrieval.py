"""Retrieve historical evidence from PostgreSQL."""

import numpy as np
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.engine import Engine

from diagnostic_assist.db_models import HistoricalCaseRecord
from diagnostic_assist.embedding_store import DIMENSIONS, MODEL_NAME
from diagnostic_assist.models import HistoricalCase
from diagnostic_assist.retrieval import Embedder
from sqlalchemy import func, select

from diagnostic_assist.models import (
    EvidenceBundle,
    EvidenceHit,
    HistoricalCase,
    SearchHit,
)
from diagnostic_assist.retrieval import (
    Embedder,
    reciprocal_rank_fusion,
    tokenize,
)

class SemanticMatch(BaseModel):
    case: HistoricalCase
    similarity: float


def search_semantic_cases(
    engine: Engine,
    embedder: Embedder,
    query: str,
    organisation_id: str,
    equipment_type: str,
    limit: int = 5,
    exclude_case_ids: set[str] | None = None,
) -> list[SemanticMatch]:
    """Search stored vectors using cosine distance."""
    query = query.strip()
    organisation_id = organisation_id.strip()
    equipment_type = equipment_type.strip()

    if not query or not organisation_id or not equipment_type:
        raise ValueError(
            "query, organisation_id and equipment_type must not be blank"
        )

    if limit < 1:
        raise ValueError("limit must be positive")

    vectors = np.asarray(embedder.encode([query]), dtype=np.float32)

    if vectors.shape != (1, DIMENSIONS):
        raise ValueError("Unexpected query embedding dimensions")

    if not np.isfinite(vectors).all():
        raise ValueError("Query embedding contains non-finite values")

    if np.linalg.norm(vectors[0]) == 0:
        raise ValueError("Query embedding must not be a zero vector")

    table = HistoricalCaseRecord.__table__
    distance = table.c.embedding.cosine_distance(vectors[0].tolist())

    # Select only the original case fields plus the retrieval score.
    case_columns = [
        table.c[name]
        for name in HistoricalCase.model_fields
    ]

    statement = (
        select(*case_columns, distance.label("distance"))
        .where(
            table.c.organisation_id == organisation_id,
            table.c.equipment_type == equipment_type,
            table.c.embedding.is_not(None),
            table.c.embedding_model == MODEL_NAME,
        )
        .order_by(distance, table.c.case_id)
        .limit(limit)
    )

    if exclude_case_ids:
        statement = statement.where(
            table.c.case_id.not_in(sorted(exclude_case_ids))
        )

    with engine.connect() as connection:
        rows = connection.execute(statement).mappings().all()

    matches = []

    for row in rows:
        case = HistoricalCase.model_validate(
            {
                name: row[name]
                for name in HistoricalCase.model_fields
            }
        )
        matches.append(
            SemanticMatch(
                case=case,
                similarity=1.0 - float(row["distance"]),
            )
        )

    return matches

class KeywordMatch(BaseModel):
    case: HistoricalCase
    score: float


def search_keyword_cases(
    engine: Engine,
    query: str,
    organisation_id: str,
    equipment_type: str,
    limit: int = 5,
    exclude_case_ids: set[str] | None = None,
) -> list[KeywordMatch]:
    query = query.strip()
    organisation_id = organisation_id.strip()
    equipment_type = equipment_type.strip()

    if not query or not organisation_id or not equipment_type:
        raise ValueError(
            "query, organisation_id and equipment_type must not be blank"
        )

    if limit < 1:
        raise ValueError("limit must be positive")

    tokens = list(dict.fromkeys(tokenize(query)))

    if not tokens:
        return []

    # Match any normalized token. Quoting treats tokens as literal terms.
    query_text = " OR ".join(f'"{token}"' for token in tokens)
    ts_query = func.websearch_to_tsquery("simple", query_text)

    table = HistoricalCaseRecord.__table__
    score = func.ts_rank_cd(table.c.search_vector, ts_query)

    case_columns = [
        table.c[name]
        for name in HistoricalCase.model_fields
    ]

    statement = (
        select(*case_columns, score.label("score"))
        .where(
            table.c.organisation_id == organisation_id,
            table.c.equipment_type == equipment_type,
            table.c.search_vector.op("@@")(ts_query),
        )
        .order_by(score.desc(), table.c.case_id)
        .limit(limit)
    )

    if exclude_case_ids:
        statement = statement.where(
            table.c.case_id.not_in(sorted(exclude_case_ids))
        )

    with engine.connect() as connection:
        rows = connection.execute(statement).mappings().all()

    return [
        KeywordMatch(
            case=HistoricalCase.model_validate(
                {
                    name: row[name]
                    for name in HistoricalCase.model_fields
                }
            ),
            score=float(row["score"]),
        )
        for row in rows
    ]

def search_hybrid_cases(
    engine: Engine,
    embedder: Embedder,
    query: str,
    organisation_id: str,
    equipment_type: str,
    limit: int = 5,
    candidate_depth: int = 5,
    exclude_case_ids: set[str] | None = None,
) -> EvidenceBundle:
    if limit < 1 or candidate_depth < 1:
        raise ValueError("limit and candidate_depth must be positive")

    keyword_matches = search_keyword_cases(
        engine=engine,
        query=query,
        organisation_id=organisation_id,
        equipment_type=equipment_type,
        limit=candidate_depth,
        exclude_case_ids=exclude_case_ids,
    )

    semantic_matches = search_semantic_cases(
        engine=engine,
        embedder=embedder,
        query=query,
        organisation_id=organisation_id,
        equipment_type=equipment_type,
        limit=candidate_depth,
        exclude_case_ids=exclude_case_ids,
    )

    keyword_ranking = [
        SearchHit(
            case_id=match.case.case_id,
            source="keyword",
            rank=rank,
            score=match.score,
        )
        for rank, match in enumerate(keyword_matches, start=1)
    ]

    semantic_ranking = [
        SearchHit(
            case_id=match.case.case_id,
            source="semantic",
            rank=rank,
            score=match.similarity,
        )
        for rank, match in enumerate(semantic_matches, start=1)
    ]

    fused = reciprocal_rank_fusion(
        [keyword_ranking, semantic_ranking],
        source_weights={"keyword": 1.0, "semantic": 2.0},
    )

    cases_by_id = {
        match.case.case_id: match.case
        for match in [*keyword_matches, *semantic_matches]
    }

    hits = [
        EvidenceHit(
            case=cases_by_id[result.case_id],
            rrf_score=result.rrf_score,
            source_ranks=result.source_ranks,
            match_scope="equipment_type",
        )
        for result in fused[:limit]
    ]

    return EvidenceBundle(
        query=query.strip(),
        equipment_type=equipment_type.strip(),
        hits=hits,
        used_family_fallback=False,
        warnings=(
            []
            if hits
            else ["No historical matches found for the selected equipment."]
        ),
    )