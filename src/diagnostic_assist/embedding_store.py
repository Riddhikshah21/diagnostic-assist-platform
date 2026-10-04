"""Generate and persist historical description embeddings."""

from hashlib import sha256

import numpy as np
from sqlalchemy import func, select, update
from sqlalchemy.engine import Engine

from diagnostic_assist.db_models import HistoricalCaseRecord
from diagnostic_assist.retrieval import SentenceTransformerEmbedder

MODEL_NAME = (
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
DIMENSIONS = 384


def generate_embeddings(
    engine: Engine,
    organisation_id: str,
    batch_size: int = 32,
) -> tuple[int, int]:
    """Return counts of updated and already-current cases."""
    organisation_id = organisation_id.strip()

    if not organisation_id:
        raise ValueError("organisation_id must not be blank")

    if batch_size < 1:
        raise ValueError("batch_size must be positive")

    table = HistoricalCaseRecord.__table__
    embedder = SentenceTransformerEmbedder(MODEL_NAME)

    updated = 0
    skipped = 0
    last_case_id = None

    while True:
        query = (
            select(
                table.c.case_id,
                table.c.customer_description,
                table.c.embedding_model,
                table.c.embedding_text_hash,
                table.c.embedding.is_not(None).label("has_embedding"),
            )
            .where(table.c.organisation_id == organisation_id)
            .order_by(table.c.case_id)
            .limit(batch_size)
        )

        if last_case_id is not None:
            query = query.where(table.c.case_id > last_case_id)

        with engine.connect() as connection:
            rows = connection.execute(query).mappings().all()

        if not rows:
            break

        last_case_id = rows[-1]["case_id"]
        pending = []

        for row in rows:
            text_hash = sha256(
                row["customer_description"].encode("utf-8")
            ).hexdigest()

            if (
                row["has_embedding"]
                and row["embedding_model"] == MODEL_NAME
                and row["embedding_text_hash"] == text_hash
            ):
                skipped += 1
            else:
                pending.append((row, text_hash))

        if not pending:
            continue

        vectors = embedder.encode(
            [row["customer_description"] for row, _ in pending]
        )

        if vectors.shape != (len(pending), DIMENSIONS):
            raise ValueError("Embedding model returned unexpected dimensions")

        if not np.isfinite(vectors).all():
            raise ValueError("Embedding model returned non-finite values")

        if np.any(np.linalg.norm(vectors, axis=1) == 0):
            raise ValueError("Embedding model returned a zero vector")

        with engine.begin() as connection:
            for (row, text_hash), vector in zip(pending, vectors):
                statement = (
                    update(table)
                    .where(
                        table.c.organisation_id == organisation_id,
                        table.c.case_id == row["case_id"],
                        table.c.customer_description
                        == row["customer_description"],
                    )
                    .values(
                        embedding=vector.tolist(),
                        embedding_model=MODEL_NAME,
                        embedding_text_hash=text_hash,
                        embedding_updated_at=func.now(),
                    )
                )

                result = connection.execute(statement)

                if result.rowcount != 1:
                    raise RuntimeError(
                        "A case changed during embedding. Rerun the command."
                    )

        updated += len(pending)

    return updated, skipped