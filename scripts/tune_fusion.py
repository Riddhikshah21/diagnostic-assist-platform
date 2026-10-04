"""Compare fusion settings on development or validation queries."""

import argparse
import json
from dataclasses import asdict
from itertools import product
from pathlib import Path

from diagnostic_assist.evaluation import (
    EvaluationLoadError,
    load_evaluation_queries,
)
from diagnostic_assist.loader import CaseLoadError, load_cases
from diagnostic_assist.metrics import score_ranking
from diagnostic_assist.retrieval import (
    KeywordIndex,
    SemanticIndex,
    SentenceTransformerEmbedder,
    reciprocal_rank_fusion,
)

ROOT = Path(__file__).resolve().parents[1]


def mean_or_none(values):
    return sum(values) / len(values) if values else None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare RRF settings without using the test split."
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=ROOT / "tests/fixtures/synthetic_cases.json",
    )
    parser.add_argument(
        "--queries",
        type=Path,
        default=ROOT / "evaluation/queries.json",
    )
    parser.add_argument(
        "--split",
        choices=["development", "validation"],
        default="development",
    )
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument(
        "--depths",
        type=int,
        nargs="+",
        default=[3, 5, 10],
    )
    parser.add_argument(
        "--weights",
        type=float,
        nargs="+",
        default=[1.0, 2.0, 3.0],
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.k < 1 or any(depth < 1 for depth in args.depths):
        parser.error("k and candidate depths must be positive")

    if any(not 0 < weight < float("inf") for weight in args.weights):
        parser.error("Weights must be finite and positive")

    try:
        cases = load_cases(args.data)
        queries = load_evaluation_queries(args.queries, cases)
    except (CaseLoadError, EvaluationLoadError) as exc:
        parser.error(str(exc))

    queries = [query for query in queries if query.split == args.split]

    if not queries:
        parser.error(f"No queries found for split: {args.split}")

    candidates_by_query = {}

    for query in queries:
        candidates = {
            case.case_id
            for case in cases
            if case.equipment_type == query.equipment_type
            and case.case_id not in query.exclude_case_ids
        }

        outside_scope = set(query.relevant_case_ids) - candidates

        if outside_scope:
            parser.error(
                f"{query.query_id}: relevant cases outside exact-type scope: "
                + ", ".join(sorted(outside_scope))
            )

        candidates_by_query[query.query_id] = candidates

    print("Building indexes with the real multilingual model...")

    keyword = KeywordIndex(cases)
    semantic = SemanticIndex(cases, SentenceTransformerEmbedder())

    # Retrieve once, then reuse candidates for every configuration.
    prepared = {}

    for query in queries:
        candidate_ids = candidates_by_query[query.query_id]

        prepared[query.query_id] = (
            keyword.search(
                query.query,
                candidate_ids=candidate_ids,
                limit=max(args.depths),
            ),
            semantic.search(
                query.query,
                candidate_ids=candidate_ids,
                limit=max(args.depths),
            ),
        )

    results = []

    for depth, weight in product(args.depths, args.weights):
        query_results = []

        for query in queries:
            keyword_hits, semantic_hits = prepared[query.query_id]

            fused = reciprocal_rank_fusion(
                [keyword_hits[:depth], semantic_hits[:depth]],
                source_weights={"bm25": 1.0, "semantic": weight},
            )
            case_ids = [hit.case_id for hit in fused[:args.k]]

            query_results.append(
                {
                    "query_id": query.query_id,
                    "case_ids": case_ids,
                    "metrics": asdict(
                        score_ranking(
                            case_ids,
                            query.relevant_case_ids,
                            k=args.k,
                        )
                    ),
                }
            )

        positive = [
            row["metrics"]
            for row in query_results
            if not row["metrics"]["is_negative_query"]
        ]
        negative = [
            row["metrics"]
            for row in query_results
            if row["metrics"]["is_negative_query"]
        ]

        summary = {
            "candidate_depth": depth,
            "semantic_weight": weight,
            "positive_queries": len(positive),
            "negative_queries": len(negative),
            "precision_at_k": mean_or_none(
                [row["precision_at_k"] for row in positive]
            ),
            "recall_at_k": mean_or_none(
                [row["recall_at_k"] for row in positive]
            ),
            "mrr_at_k": mean_or_none(
                [row["reciprocal_rank_at_k"] for row in positive]
            ),
            "negative_query_return_rate": mean_or_none(
                [float(row["has_results"]) for row in negative]
            ),
        }

        results.append(
            {"summary": summary, "queries": query_results}
        )
        print(json.dumps(summary))

    report = {
        "data": str(args.data),
        "queries": str(args.queries),
        "split": args.split,
        "scope": "exact_equipment_type",
        "k": args.k,
        "bm25_weight": 1.0,
        "rank_constant": 60,
        "results": results,
    }

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Report saved to {args.output}")


if __name__ == "__main__":
    main()