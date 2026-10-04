"""Search historical cases stored in PostgreSQL."""

import argparse
import json

from diagnostic_assist.database import create_database_engine
from diagnostic_assist.db_retrieval import search_semantic_cases
from diagnostic_assist.embedding_store import MODEL_NAME
from diagnostic_assist.retrieval import SentenceTransformerEmbedder


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search stored historical case embeddings."
    )
    parser.add_argument("--query", required=True)
    parser.add_argument("--organisation-id", required=True)
    parser.add_argument("--equipment-type", required=True)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument(
        "--exclude-case-id",
        action="append",
        default=[],
    )
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be positive")

    engine = create_database_engine()
    embedder = SentenceTransformerEmbedder(MODEL_NAME)

    try:
        matches = search_semantic_cases(
            engine=engine,
            embedder=embedder,
            query=args.query,
            organisation_id=args.organisation_id,
            equipment_type=args.equipment_type,
            limit=args.limit,
            exclude_case_ids=set(args.exclude_case_id),
        )
    finally:
        engine.dispose()

    print(
        json.dumps(
            {
                "query": args.query,
                "equipment_type": args.equipment_type,
                "retrieval_method": "semantic",
                "hits": [
                    match.model_dump(mode="json")
                    for match in matches
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()