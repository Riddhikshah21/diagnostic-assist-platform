import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pytest

from diagnostic_assist.metrics import score_ranking
from scripts import evaluate

ROOT = Path(__file__).parents[1]
CASE_FILE = ROOT / "tests/fixtures/synthetic_cases.json"
QUERY_FILE = ROOT / "evaluation/queries.json"


class ConstantEmbedder:
    """Tests report plumbing, not semantic retrieval quality."""

    def encode(self, texts):
        return np.ones((len(texts), 2), dtype=np.float32)


def make_row(retrieved, relevant, k=2):
    metrics = asdict(score_ranking(retrieved, relevant, k=k))
    return {
        "rankings": {
            method: {"metrics": metrics}
            for method in evaluate.METHODS
        }
    }


def test_summary_separates_positive_and_negative_queries() -> None:
    rows = [
        make_row(["A"], {"A"}),
        make_row(["X"], {"A"}),
        make_row(["X"], set()),
        make_row([], set()),
    ]

    summary = evaluate.summarize(rows)

    for method in evaluate.METHODS:
        result = summary[method]

        assert result["positive_queries"] == 2
        assert result["negative_queries"] == 2
        assert result["precision_at_k"] == 0.25
        assert result["recall_at_k"] == 0.5
        assert result["mrr_at_k"] == 0.5
        assert result["negative_query_return_rate"] == 0.5


def test_empty_summary_does_not_invent_scores() -> None:
    summary = evaluate.summarize([])

    for method in evaluate.METHODS:
        result = summary[method]

        assert result["positive_queries"] == 0
        assert result["negative_queries"] == 0
        assert result["precision_at_k"] is None
        assert result["recall_at_k"] is None
        assert result["mrr_at_k"] is None
        assert result["negative_query_return_rate"] is None


def test_runner_writes_report_without_real_model(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output = tmp_path / "reports" / "baseline.json"

    monkeypatch.setattr(
        evaluate,
        "SentenceTransformerEmbedder",
        ConstantEmbedder,
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluate.py",
            "--data",
            str(CASE_FILE),
            "--queries",
            str(QUERY_FILE),
            "--output",
            str(output),
        ],
    )

    evaluate.main()

    report = json.loads(output.read_text(encoding="utf-8"))

    assert len(report["results"]) == 6
    assert set(report["by_language"]) == {"en", "de", "fr", "it"}
    assert report["configuration"]["scope"] == "exact_equipment_type"

    first_query = next(
        row for row in report["results"]
        if row["query_id"] == "Q-001"
    )

    for method in evaluate.METHODS:
        assert "S-001" not in first_query["rankings"][method]["case_ids"]

    assert (
        report["summary"]["semantic"]["negative_query_return_rate"]
        == 1.0
    )


def test_missing_judgment_case_fails_before_model_loading(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    queries = json.loads(QUERY_FILE.read_text(encoding="utf-8"))
    queries[0]["relevant_case_ids"] = ["S-MISSING"]

    query_file = tmp_path / "queries.json"
    query_file.write_text(json.dumps(queries), encoding="utf-8")

    def unexpected_model_load():
        raise AssertionError("Model must not load for invalid judgments")

    monkeypatch.setattr(
        evaluate,
        "SentenceTransformerEmbedder",
        unexpected_model_load,
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluate.py",
            "--data",
            str(CASE_FILE),
            "--queries",
            str(query_file),
        ],
    )

    with pytest.raises(SystemExit) as error:
        evaluate.main()

    assert error.value.code == 2
    assert "references missing cases" in capsys.readouterr().err