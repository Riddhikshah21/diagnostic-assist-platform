from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from typing import Self

from pydantic import field_validator, model_validator
from diagnostic_assist.models import EvidenceBundle

class SessionCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    equipment_type: str = Field(min_length=1)
    initial_description: str = Field(min_length=1)

class SessionEvidenceResponse(BaseModel):
    session_id: UUID
    revision: int = Field(ge=1)
    evidence: EvidenceBundle
    
class ObservationCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    question: str | None = None
    answer: str | None = None
    is_unknown: bool = False

    @field_validator("question", "answer")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @model_validator(mode="after")
    def validate_answer(self) -> Self:
        if self.is_unknown:
            if self.answer is not None:
                raise ValueError("Unknown answers must have answer=null")

            if self.question is None:
                raise ValueError("Provide a question for an unknown answer")
        elif self.answer is None:
            raise ValueError("A known answer must contain text")

        return self
    
class ObservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    observation_id: UUID
    question: str | None
    answer: str | None
    is_unknown: bool
    created_at: datetime


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: UUID
    equipment_type: str
    initial_description: str
    status: Literal["active", "completed"]
    revision: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime
    observations: list[ObservationResponse] = Field(default_factory=list)