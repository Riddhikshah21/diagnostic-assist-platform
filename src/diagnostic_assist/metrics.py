"""Retrieval metrics; these are not diagnostic probabilities."""

from collections.abc import Collection, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalMetrics:
    precision_at_k: float
    recall_at_k: float | None
    reciprocal_rank_at_k: float | None
    has_results: bool
    is_negative_query: bool


def score_ranking(
    retrieved_case_ids: Sequence[str],
    relevant_case_ids: Collection[str],
    k: int = 5,
) -> RetrievalMetrics:
    """Score a ranking against manually supplied relevance judgments.

    Precision uses k as its denominator, including unfilled positions.
    Recall and reciprocal rank are undefined for negative queries.
    """

    if k < 1:
        raise ValueError("k must be positive")

    if len(retrieved_case_ids) != len(set(retrieved_case_ids)):
        raise ValueError("Retrieved case IDs must be unique")

    top_ids = list(retrieved_case_ids[:k])
    relevant_ids = set(relevant_case_ids)
    found = set(top_ids) & relevant_ids

    precision = len(found) / k

    if not relevant_ids:
        return RetrievalMetrics(
            precision_at_k=precision,
            recall_at_k=None,
            reciprocal_rank_at_k=None,
            has_results=bool(top_ids),
            is_negative_query=True,
        )

    reciprocal_rank = next(
        (
            1.0 / rank
            for rank, case_id in enumerate(top_ids, start=1)
            if case_id in relevant_ids
        ),
        0.0,
    )

    return RetrievalMetrics(
        precision_at_k=precision,
        recall_at_k=len(found) / len(relevant_ids),
        reciprocal_rank_at_k=reciprocal_rank,
        has_results=bool(top_ids),
        is_negative_query=False,
    )