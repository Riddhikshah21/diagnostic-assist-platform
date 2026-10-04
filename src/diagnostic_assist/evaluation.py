"""Load retrieval queries and relevance judgments.

These records describe retrieval relevance, not diagnostic causes.
"""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from diagnostic_assist.models import HistoricalCase


class EvaluationLoadError(ValueError):
    """Raised when evaluation data is invalid or inconsistent."""


class EvaluationQuery(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    query_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    language: str = Field(min_length=2)
    equipment_type: str = Field(min_length=1)
    equipment_family: str | None = None
    relevant_case_ids: list[str]
    exclude_case_ids: list[str] = Field(default_factory=list)
    category: str = Field(min_length=1)
    split: Literal["development", "validation", "test"]

    @field_validator("equipment_family")
    @classmethod
    def normalize_family(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("relevant_case_ids", "exclude_case_ids")
    @classmethod
    def validate_case_ids(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]

        if any(not value for value in cleaned):
            raise ValueError("Case IDs must not be blank")

        if len(cleaned) != len(set(cleaned)):
            raise ValueError("Case IDs must not contain duplicates")

        return cleaned

    @model_validator(mode="after")
    def validate_judgments(self) -> Self:
        overlap = set(self.relevant_case_ids) & set(self.exclude_case_ids)

        if overlap:
            raise ValueError(
                "Relevant cases cannot also be excluded: "
                + ", ".join(sorted(overlap))
            )

        return self


def load_evaluation_queries(
    path: str | Path,
    cases: Sequence[HistoricalCase] | None = None,
) -> list[EvaluationQuery]:
    """Load queries and optionally check IDs against the case corpus."""

    source = Path(path)

    try:
        with source.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvaluationLoadError(
            f"Cannot read evaluation file {source}: {exc}"
        ) from exc

    if not isinstance(payload, list) or not payload:
        raise EvaluationLoadError(
            "Evaluation data must be a non-empty JSON array"
        )

    queries: list[EvaluationQuery] = []
    seen_query_ids: set[str] = set()
    available_ids = (
        {case.case_id for case in cases}
        if cases is not None
        else None
    )

    for index, record in enumerate(payload, start=1):
        try:
            query = EvaluationQuery.model_validate(record)
        except ValidationError as exc:
            raise EvaluationLoadError(
                f"Invalid evaluation record {index}: {exc}"
            ) from exc

        if query.query_id in seen_query_ids:
            raise EvaluationLoadError(
                f"Duplicate query ID: {query.query_id}"
            )

        if available_ids is not None:
            referenced_ids = (
                set(query.relevant_case_ids)
                | set(query.exclude_case_ids)
            )
            missing_ids = referenced_ids - available_ids

            if missing_ids:
                raise EvaluationLoadError(
                    f"{query.query_id} references missing cases: "
                    + ", ".join(sorted(missing_ids))
                )

        seen_query_ids.add(query.query_id)
        queries.append(query)

    return queries