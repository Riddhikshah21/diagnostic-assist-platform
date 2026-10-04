"""Evaluate retrieval using external queries and relevance judgments."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

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
METHODS = ("bm25", "semantic", "rrf")


def mean_or_none(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def summarize(rows: list[dict]) -> dict:
    summary = {}

    for method in METHODS:
        positive = [
            row["rankings"][method]["metrics"]
            for row in rows
            if not row["rankings"][method]["metrics"]["is_negative_query"]
        ]
        negative = [
            row["rankings"][method]["metrics"]
            for row in rows
            if row["rankings"][method]["metrics"]["is_negative_query"]
        ]

        summary[method] = {
            "positive_queries": len(positive),
            "negative_queries": len(negative),
            "precision_at_k": mean_or_none(
                [item["precision_at_k"] for item in positive]
            ),
            "recall_at_k": mean_or_none(
                [item["recall_at_k"] for item in positive]
            ),
            "mrr_at_k": mean_or_none(
                [item["reciprocal_rank_at_k"] for item in positive]
            ),
            "negative_query_return_rate": mean_or_none(
                [float(item["has_results"]) for item in negative]
            ),
        }

    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate multilingual retrieval judgments."
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
        choices=["development", "validation", "test"],
        default="development",
    )
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--candidate-depth", type=int, default=5)
    parser.add_argument("--semantic-weight", type=float, default=2.0)
    parser.add_argument("--output", type=Path)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.k < 1 or args.candidate_depth < 1:
        parser.error("--k and --candidate-depth must be positive")

    if not 0 < args.semantic_weight < float("inf"):
        parser.error("--semantic-weight must be finite and positive")

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

    setup_start = perf_counter()
    keyword = KeywordIndex(cases)
    semantic = SemanticIndex(cases, SentenceTransformerEmbedder())
    setup_seconds = perf_counter() - setup_start

    rows = []

    for query in queries:
        candidate_ids = candidates_by_query[query.query_id]
        started = perf_counter()

        # Each single-source baseline gets enough results to measure @k.
        # Fusion uses its independently configured candidate depth.
        source_limit = max(args.k, args.candidate_depth)

        keyword_hits = keyword.search(
            query.query,
            candidate_ids=candidate_ids,
            limit=source_limit,
        )
        semantic_hits = semantic.search(
            query.query,
            candidate_ids=candidate_ids,
            limit=source_limit,
        )
        fused_hits = reciprocal_rank_fusion(
            [
                keyword_hits[:args.candidate_depth],
                semantic_hits[:args.candidate_depth],
            ],
            source_weights={
                "bm25": 1.0,
                "semantic": args.semantic_weight,
            },
        )

        elapsed_seconds = perf_counter() - started

        rankings = {
            "bm25": [hit.case_id for hit in keyword_hits[:args.k]],
            "semantic": [hit.case_id for hit in semantic_hits[:args.k]],
            "rrf": [hit.case_id for hit in fused_hits[:args.k]],
        }

        rows.append(
            {
                "query_id": query.query_id,
                "query": query.query,
                "language": query.language,
                "category": query.category,
                "equipment_type": query.equipment_type,
                "combined_search_seconds": elapsed_seconds,
                "rankings": {
                    method: {
                        "case_ids": case_ids,
                        "metrics": asdict(
                            score_ranking(
                                case_ids,
                                query.relevant_case_ids,
                                k=args.k,
                            )
                        ),
                    }
                    for method, case_ids in rankings.items()
                },
            }
        )

        print(
            f"{query.query_id} [{query.language}] "
            f"RRF results: {', '.join(rankings['rrf']) or 'none'}"
        )

    report = {
        "configuration": {
            "data": str(args.data),
            "queries": str(args.queries),
            "split": args.split,
            "k": args.k,
            "candidate_depth": args.candidate_depth,
            "semantic_weight": args.semantic_weight,
            "scope": "exact_equipment_type",
            "model": (
                "sentence-transformers/"
                "paraphrase-multilingual-MiniLM-L12-v2"
            ),
        },
        "index_setup_seconds": setup_seconds,
        "summary": summarize(rows),
        "by_language": {
            language: summarize(
                [row for row in rows if row["language"] == language]
            )
            for language in sorted({row["language"] for row in rows})
        },
        "results": rows,
    }

    print("\nSummary")
    print(json.dumps(report["summary"], indent=2))

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"\nReport saved to {args.output}")


if __name__ == "__main__":
    main()