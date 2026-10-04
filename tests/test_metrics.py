import pytest

from diagnostic_assist.metrics import score_ranking


def test_perfect_ranking() -> None:
    result = score_ranking(["A", "B"], {"A", "B"}, k=2)

    assert result.precision_at_k == 1.0
    assert result.recall_at_k == 1.0
    assert result.reciprocal_rank_at_k == 1.0


def test_partial_ranking_and_cutoff() -> None:
    result = score_ranking(
        ["X", "A", "B"],
        {"A", "B"},
        k=2,
    )

    assert result.precision_at_k == 0.5
    assert result.recall_at_k == 0.5
    assert result.reciprocal_rank_at_k == 0.5


def test_unfilled_positions_count_as_precision_misses() -> None:
    result = score_ranking(["A"], {"A"}, k=5)

    assert result.precision_at_k == 0.2
    assert result.recall_at_k == 1.0


def test_no_results_for_positive_query() -> None:
    result = score_ranking([], {"A"}, k=5)

    assert result.precision_at_k == 0.0
    assert result.recall_at_k == 0.0
    assert result.reciprocal_rank_at_k == 0.0
    assert result.has_results is False


def test_negative_query_with_no_results() -> None:
    result = score_ranking([], set(), k=5)

    assert result.is_negative_query is True
    assert result.has_results is False
    assert result.recall_at_k is None
    assert result.reciprocal_rank_at_k is None


def test_negative_query_with_unwanted_results() -> None:
    result = score_ranking(["A"], set(), k=5)

    assert result.is_negative_query is True
    assert result.has_results is True
    assert result.precision_at_k == 0.0


def test_duplicate_results_are_rejected() -> None:
    with pytest.raises(ValueError, match="must be unique"):
        score_ranking(["A", "A"], {"A"})


@pytest.mark.parametrize("k", [0, -1])
def test_invalid_cutoff_is_rejected(k: int) -> None:
    with pytest.raises(ValueError, match="must be positive"):
        score_ranking(["A"], {"A"}, k=k)