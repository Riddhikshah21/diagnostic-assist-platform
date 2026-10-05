"""Structured diagnostic suggestions generated from historical evidence."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field


class EvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    case_id: str = Field(min_length=1)
    field: Literal["technician_notes", "resolution_text"]
    quote: str = Field(min_length=1)


class CauseSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    cause: str = Field(min_length=1)
    evidence: list[EvidenceReference] = Field(min_length=1, max_length=5)

    @computed_field
    @property
    def explanation(self) -> str:
        return "\n".join(
            f'Historical case {reference.case_id}: "{reference.quote}"'
            for reference in self.evidence
        )

class DiagnosticDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    summary: str = Field(min_length=1)
    possible_causes: list[CauseSuggestion] = Field(max_length=3)
    follow_up_question: str | None = Field(max_length=180)
    limitations: list[str] = Field(max_length=5)