"""Persist validated historical cases."""

from collections.abc import Sequence

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy import case
from diagnostic_assist.db_models import HistoricalCaseRecord
from diagnostic_assist.models import HistoricalCase
from diagnostic_assist.retrieval import tokenize

def import_cases(
    engine: Engine,
    cases: Sequence[HistoricalCase],
    organisation_id: str,
) -> int:
    """Insert or update cases in one transaction.

    Returns the number processed, not the number newly inserted.
    """
    organisation_id = organisation_id.strip()

    if not organisation_id:
        raise ValueError("organisation_id must not be blank")

    case_ids = [case.case_id for case in cases]

    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Import contains duplicate case IDs")

    if not cases:
        return 0

    rows = [
        {
            **case.model_dump(),
            "organisation_id": organisation_id,
            "search_text": " ".join(
                tokenize(case.customer_description)
            ),
        }
        for case in cases
    ]

    table = HistoricalCaseRecord.__table__

    # Batch writes, but commit the whole import together.
    with engine.begin() as connection:
        for start in range(0, len(rows), 500):
            statement = insert(table).values(rows[start:start + 500])

            updates = {
                name: statement.excluded[name]
                for name in rows[0]
                if name not in {"organisation_id", "case_id"}
            }

            description_changed = (
                table.c.customer_description.is_distinct_from(
                    statement.excluded.customer_description
                )
            )

            for column_name in (
                "embedding",
                "embedding_model",
                "embedding_text_hash",
                "embedding_updated_at",
            ):
                updates[column_name] = case(
                    (description_changed, None),
                    else_=table.c[column_name],
                )

            statement = statement.on_conflict_do_update(
                index_elements=["organisation_id", "case_id"],
                set_=updates,
            )

            connection.execute(statement)

    return len(rows)