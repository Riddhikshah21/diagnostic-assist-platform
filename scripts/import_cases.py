"""Import a JSON case file into PostgreSQL."""

import argparse
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from diagnostic_assist.database import create_database_engine
from diagnostic_assist.ingestion import import_cases
from diagnostic_assist.loader import CaseLoadError, load_cases


def main() -> None:
    parser = argparse.ArgumentParser(description="Import historical cases.")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--organisation-id", required=True)
    args = parser.parse_args()

    try:
        cases = load_cases(args.data)
        engine = create_database_engine()
    except (CaseLoadError, ValueError) as exc:
        parser.error(str(exc))

    try:
        processed = import_cases(
            engine=engine,
            cases=cases,
            organisation_id=args.organisation_id,
        )
    except ValueError as exc:
        parser.error(str(exc))
    except SQLAlchemyError as exc:
        parser.exit(
            1,
            f"Database import failed ({type(exc).__name__}). "
            "Check the database connection and migrations.\n",
        )
    finally:
        engine.dispose()

    print(
        f"Processed {processed} cases "
        f"for organisation {args.organisation_id.strip()}."
    )


if __name__ == "__main__":
    main()