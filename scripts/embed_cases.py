"""Generate embeddings for cases already stored in PostgreSQL."""

import argparse

from diagnostic_assist.database import create_database_engine
from diagnostic_assist.embedding_store import generate_embeddings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate and store description embeddings."
    )
    parser.add_argument("--organisation-id", required=True)
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()

    if args.batch_size < 1:
        parser.error("--batch-size must be positive")

    engine = create_database_engine()

    try:
        updated, skipped = generate_embeddings(
            engine,
            organisation_id=args.organisation_id,
            batch_size=args.batch_size,
        )
    finally:
        engine.dispose()

    print(f"Updated: {updated}")
    print(f"Already current: {skipped}")

    if updated == 0 and skipped == 0:
        print("No cases found for this organisation.")


if __name__ == "__main__":
    main()