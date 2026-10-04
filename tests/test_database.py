import os
from hashlib import sha256
from uuid import uuid4

import numpy as np
import pytest
from sqlalchemy import delete, func, select, update

from diagnostic_assist.database import create_database_engine
from diagnostic_assist.db_models import HistoricalCaseRecord
from diagnostic_assist.db_retrieval import (
    search_hybrid_cases,
    search_keyword_cases,
    search_semantic_cases,
)
from diagnostic_assist.embedding_store import DIMENSIONS, MODEL_NAME
from diagnostic_assist.ingestion import import_cases
from diagnostic_assist.models import HistoricalCase


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_TESTS") != "1",
    reason="Set RUN_DB_TESTS=1 to test the local database.",
)


class TestEmbedder:
    """Fixed vectors for database behaviour tests."""

    def encode(self, texts):
        vectors = np.zeros((len(texts), DIMENSIONS), dtype=np.float32)
        vectors[:, 0] = 1.0
        return vectors


def make_case(case_id, description, equipment_type="TEST-100"):
    return HistoricalCase(
        case_id=case_id,
        equipment_family="Test Equipment",
        equipment_type=equipment_type,
        created_at="2026-01-01T00:00:00Z",
        language="en",
        customer_description=description,
        technician_notes="Connection tested OK.",
        parts_replaced=[],
        resolution_text="Test outcome.",
    )


@pytest.fixture
def stored_cases():
    engine = create_database_engine()
    organisation = f"test-{uuid4().hex}"
    other_organisation = f"test-{uuid4().hex}"
    table = HistoricalCaseRecord.__table__

    cases = [
        make_case("T-001", "Motor overheating with ALERT-901."),
        make_case("T-002", "Motor overheating with ALERT901."),
        make_case(
            "T-003",
            "Hydraulic leak.",
            equipment_type="TEST-OTHER",
        ),
    ]
    other_cases = [
        make_case("T-001", "Another organisation's case.")
    ]

    try:
        import_cases(engine, cases, organisation)
        import_cases(engine, other_cases, other_organisation)

        for owner, records in (
            (organisation, cases),
            (other_organisation, other_cases),
        ):
            with engine.begin() as connection:
                for record in records:
                    vector = np.zeros(DIMENSIONS, dtype=np.float32)
                    vector[0] = 1.0

                    connection.execute(
                        update(table)
                        .where(
                            table.c.organisation_id == owner,
                            table.c.case_id == record.case_id,
                        )
                        .values(
                            embedding=vector.tolist(),
                            embedding_model=MODEL_NAME,
                            embedding_text_hash=sha256(
                                record.customer_description.encode("utf-8")
                            ).hexdigest(),
                            embedding_updated_at=func.now(),
                        )
                    )

        yield engine, organisation, cases
    finally:
        try:
            with engine.begin() as connection:
                connection.execute(
                    delete(table).where(
                        table.c.organisation_id.in_(
                            [organisation, other_organisation]
                        )
                    )
                )
        finally:
            engine.dispose()


def test_reimport_preserves_rows_and_embeddings(stored_cases):
    engine, organisation, cases = stored_cases
    table = HistoricalCaseRecord.__table__

    import_cases(engine, cases, organisation)

    with engine.connect() as connection:
        counts = connection.execute(
            select(
                func.count(),
                func.count(table.c.embedding),
            )
            .select_from(table)
            .where(table.c.organisation_id == organisation)
        ).one()

    assert tuple(counts) == (3, 3)


def test_changed_description_clears_old_embedding(stored_cases):
    engine, organisation, cases = stored_cases
    table = HistoricalCaseRecord.__table__

    changed = cases[0].model_copy(
        update={"customer_description": "Different reported symptom."}
    )
    import_cases(engine, [changed], organisation)

    with engine.connect() as connection:
        row = connection.execute(
            select(
                table.c.embedding,
                table.c.embedding_model,
                table.c.embedding_text_hash,
                table.c.embedding_updated_at,
            ).where(
                table.c.organisation_id == organisation,
                table.c.case_id == changed.case_id,
            )
        ).one()

    assert all(value is None for value in row)


def test_semantic_search_filters_organisation_and_equipment(stored_cases):
    engine, organisation, _ = stored_cases

    matches = search_semantic_cases(
        engine,
        TestEmbedder(),
        query="Motor overheating",
        organisation_id=organisation,
        equipment_type="TEST-100",
    )

    assert {match.case.case_id for match in matches} == {
        "T-001", "T-002"
    }
    assert all(
        match.case.customer_description.startswith("Motor")
        for match in matches
    )


def test_semantic_search_respects_exclusion(stored_cases):
    engine, organisation, _ = stored_cases

    matches = search_semantic_cases(
        engine,
        TestEmbedder(),
        query="Motor overheating",
        organisation_id=organisation,
        equipment_type="TEST-100",
        exclude_case_ids={"T-001"},
    )

    assert [match.case.case_id for match in matches] == ["T-002"]


def test_keyword_search_matches_code_variants(stored_cases):
    engine, organisation, _ = stored_cases

    matches = search_keyword_cases(
        engine,
        query="ALERT-901",
        organisation_id=organisation,
        equipment_type="TEST-100",
    )

    assert {match.case.case_id for match in matches} == {
        "T-001", "T-002"
    }


def test_hybrid_search_returns_fused_evidence(stored_cases):
    engine, organisation, _ = stored_cases

    result = search_hybrid_cases(
        engine,
        TestEmbedder(),
        query="ALERT-901",
        organisation_id=organisation,
        equipment_type="TEST-100",
        candidate_depth=5,
        limit=5,
    )

    assert len(result.hits) == 2
    assert {hit.case.case_id for hit in result.hits} == {
        "T-001", "T-002"
    }
    assert all(
        set(hit.source_ranks) == {"keyword", "semantic"}
        for hit in result.hits
    )
    assert all(hit.rrf_score > 0 for hit in result.hits)
    assert all(
        hit.case.technician_notes == "Connection tested OK."
        for hit in result.hits
    )