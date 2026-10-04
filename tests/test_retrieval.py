from collections.abc import Sequence
from pathlib import Path

import numpy as np

from diagnostic_assist.loader import load_cases
from diagnostic_assist.models import SearchHit
from diagnostic_assist.retrieval import (
    HybridRetriever,
    KeywordIndex,
    reciprocal_rank_fusion,
    tokenize,
)

DATA_FILE = Path(__file__).parent / "fixtures" / "synthetic_cases.json"


class ControlledEmbedder:
    """Deterministic vectors for behaviour tests, not model evaluation."""

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        return np.asarray(
            [self._vector(text) for text in texts],
            dtype=np.float32,
        )

    @staticmethod
    def _vector(text: str) -> list[float]:
        value = text.casefold()

        term_groups = (
            (
                "start",
                "panel",
                "display",
                "crank",
                "power up",
                "maschine startet",
                "anzeige",
            ),
            ("battery", "batterie"),
            (
                "overheat",
                "surriscalda",
                "e-207",
                "e207",
                "rattl",
                "rumore metallico",
            ),
            ("leak", "fuite", "drip", "leckt", "spraying"),
        )

        vector = [
            float(any(term in value for term in terms))
            for terms in term_groups
        ]

        if not any(vector):
            vector[3] = 0.1

        return vector


def test_loads_all_synthetic_cases() -> None:
    cases = load_cases(DATA_FILE)

    assert len(cases) == 9
    assert len({case.case_id for case in cases}) == 9


def test_tokenizer_preserves_and_normalizes_error_code() -> None:
    tokens = tokenize("Panel shows E-207.")

    assert "e-207" in tokens
    assert "e207" in tokens


def test_bm25_finds_both_error_code_formats() -> None:
    index = KeywordIndex(load_cases(DATA_FILE))

    results = index.search("E-207", limit=5)
    case_ids = {result.case_id for result in results}

    assert "S-005" in case_ids
    assert "S-006" in case_ids


def test_keyword_search_does_not_use_resolution_text() -> None:
    index = KeywordIndex(load_cases(DATA_FILE))

    # This word occurs only in outcome evidence.
    results = index.search("retorqued", limit=5)

    assert results == []


def test_query_case_can_be_excluded() -> None:
    retriever = HybridRetriever(
        load_cases(DATA_FILE),
        ControlledEmbedder(),
    )

    result = retriever.search(
        query="Machine will not start; control panel has no lights.",
        equipment_type="COMP-100",
        equipment_family="Demo Compressor",
        limit=5,
        exclude_case_ids={"S-001"},
    )

    returned_ids = {hit.case.case_id for hit in result.hits}

    assert returned_ids
    assert "S-001" not in returned_ids


def test_semantic_weight_changes_fusion_order() -> None:
    keyword = [
        SearchHit(
            case_id="keyword-only",
            source="bm25",
            rank=1,
            score=4.0,
        )
    ]
    semantic = [
        SearchHit(
            case_id="semantic-only",
            source="semantic",
            rank=1,
            score=0.8,
        )
    ]

    results = reciprocal_rank_fusion(
        [keyword, semantic],
        source_weights={"bm25": 1.0, "semantic": 2.0},
    )

    assert results[0].case_id == "semantic-only"


def test_rrf_is_deterministic() -> None:
    keyword = [
        SearchHit(case_id="A", source="bm25", rank=1, score=5.0),
        SearchHit(case_id="B", source="bm25", rank=2, score=4.0),
    ]
    semantic = [
        SearchHit(case_id="B", source="semantic", rank=1, score=0.9),
        SearchHit(case_id="A", source="semantic", rank=2, score=0.8),
    ]

    first = reciprocal_rank_fusion([keyword, semantic])
    second = reciprocal_rank_fusion([keyword, semantic])

    assert first == second
    assert [result.case_id for result in first] == ["A", "B"]


def test_hybrid_search_returns_cross_language_case() -> None:
    retriever = HybridRetriever(
        load_cases(DATA_FILE),
        ControlledEmbedder(),
    )

    result = retriever.search(
        query="Machine will not start and the display is blank",
        equipment_type="COMP-100",
        equipment_family="Demo Compressor",
        limit=5,
    )

    case_ids = {hit.case.case_id for hit in result.hits}

    assert "S-002" in case_ids


def test_original_negation_is_preserved() -> None:
    retriever = HybridRetriever(
        load_cases(DATA_FILE),
        ControlledEmbedder(),
    )

    result = retriever.search(
        query="no crank dead panel",
        equipment_type="COMP-100",
        equipment_family="Demo Compressor",
        limit=5,
    )

    matching_hit = next(
        hit for hit in result.hits if hit.case.case_id == "S-003"
    )

    assert matching_hit.case.technician_notes is not None
    assert "Contactor tested OK" in matching_hit.case.technician_notes


def test_family_fallback_is_visible() -> None:
    retriever = HybridRetriever(
        load_cases(DATA_FILE),
        ControlledEmbedder(),
    )

    result = retriever.search(
        query="machine overheats with E207",
        equipment_type="COMP-999",
        equipment_family="Demo Compressor",
        limit=3,
    )

    assert result.hits
    assert result.used_family_fallback is True
    assert result.warnings
    assert all(
        hit.match_scope == "equipment_family"
        for hit in result.hits
    )