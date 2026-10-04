import json
from pathlib import Path

import pytest

from diagnostic_assist.evaluation import (
    EvaluationLoadError,
    load_evaluation_queries,
)
from diagnostic_assist.loader import load_cases

ROOT = Path(__file__).parents[1]
CASE_FILE = ROOT / "tests" / "fixtures" / "synthetic_cases.json"
QUERY_FILE = ROOT / "evaluation" / "queries.json"


def make_query(**overrides: object) -> dict:
    record = {
        "query_id": "Q-TEST",
        "query": "The machine will not start.",
        "language": "en",
        "equipment_type": "COMP-100",
        "equipment_family": "Demo Compressor",
        "relevant_case_ids": ["S-002"],
        "exclude_case_ids": ["S-001"],
        "category": "startup",
        "split": "development",
    }
    record.update(overrides)
    return record


def write_queries(tmp_path: Path, records: object) -> Path:
    path = tmp_path / "queries.json"
    path.write_text(
        json.dumps(records, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def test_loads_development_queries_against_corpus() -> None:
    cases = load_cases(CASE_FILE)

    queries = load_evaluation_queries(QUERY_FILE, cases)

    assert len(queries) == 6
    assert {query.language for query in queries} == {
        "en", "de", "fr", "it"
    }


def test_empty_relevance_list_is_allowed(tmp_path: Path) -> None:
    path = write_queries(
        tmp_path,
        [make_query(relevant_case_ids=[], exclude_case_ids=[])],
    )

    queries = load_evaluation_queries(path)

    assert queries[0].relevant_case_ids == []


def test_relevant_case_cannot_be_excluded(tmp_path: Path) -> None:
    path = write_queries(
        tmp_path,
        [make_query(exclude_case_ids=["S-002"])],
    )

    with pytest.raises(
        EvaluationLoadError,
        match="Relevant cases cannot also be excluded",
    ):
        load_evaluation_queries(path)


def test_duplicate_query_ids_are_rejected(tmp_path: Path) -> None:
    path = write_queries(
        tmp_path,
        [make_query(), make_query()],
    )

    with pytest.raises(
        EvaluationLoadError,
        match="Duplicate query ID",
    ):
        load_evaluation_queries(path)


def test_missing_corpus_reference_is_rejected(tmp_path: Path) -> None:
    path = write_queries(
        tmp_path,
        [make_query(relevant_case_ids=["S-MISSING"])],
    )
    cases = load_cases(CASE_FILE)

    with pytest.raises(
        EvaluationLoadError,
        match="references missing cases",
    ):
        load_evaluation_queries(path, cases)


def test_explicit_empty_corpus_rejects_references(tmp_path: Path) -> None:
    path = write_queries(tmp_path, [make_query()])

    with pytest.raises(
        EvaluationLoadError,
        match="references missing cases",
    ):
        load_evaluation_queries(path, cases=[])


@pytest.mark.parametrize(
    "overrides",
    [
        {"query": "   "},
        {"relevant_case_ids": ["S-002", "S-002"]},
        {"exclude_case_ids": [" "]},
        {"split": "unknown"},
        {"root_cause": "relay failure"},
    ],
)
def test_invalid_records_are_rejected(
    tmp_path: Path,
    overrides: dict,
) -> None:
    path = write_queries(tmp_path, [make_query(**overrides)])

    with pytest.raises(
        EvaluationLoadError,
        match="Invalid evaluation record",
    ):
        load_evaluation_queries(path)


@pytest.mark.parametrize("payload", [[], {}])
def test_invalid_top_level_data_is_rejected(
    tmp_path: Path,
    payload: object,
) -> None:
    path = write_queries(tmp_path, payload)

    with pytest.raises(
        EvaluationLoadError,
        match="non-empty JSON array",
    ):
        load_evaluation_queries(path)


def test_malformed_json_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "queries.json"
    path.write_text("{invalid", encoding="utf-8")

    with pytest.raises(
        EvaluationLoadError,
        match="Cannot read evaluation file",
    ):
        load_evaluation_queries(path)


def test_missing_file_has_clear_error(tmp_path: Path) -> None:
    with pytest.raises(
        EvaluationLoadError,
        match="Cannot read evaluation file",
    ):
        load_evaluation_queries(tmp_path / "missing.json")