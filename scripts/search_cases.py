"""Search historical cases stored in PostgreSQL."""

import argparse

from diagnostic_assist.database import create_database_engine
from diagnostic_assist.db_retrieval import search_hybrid_cases
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
    parser.add_argument("--candidate-depth", type=int, default=5)
    args = parser.parse_args()

    if args.limit < 1 or args.candidate_depth < 1:
        parser.error("--limit and --candidate-depth must be positive")

    engine = create_database_engine()
    embedder = SentenceTransformerEmbedder(MODEL_NAME)

    try:
        bundle = search_hybrid_cases(
            engine=engine,
            embedder=embedder,
            query=args.query,
            organisation_id=args.organisation_id,
            equipment_type=args.equipment_type,
            limit=args.limit,
            candidate_depth=args.candidate_depth,
            exclude_case_ids=set(args.exclude_case_id),
        )
    finally:
        engine.dispose()

    print(bundle.model_dump_json(indent=2))

if __name__ == "__main__":
    main()