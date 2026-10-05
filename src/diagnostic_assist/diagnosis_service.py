"""Prepare diagnostic drafts while preserving retrieved evidence."""

import logging
from collections.abc import Sequence
from typing import Literal, Self

from pydantic import BaseModel, model_validator

from diagnostic_assist.diagnosis import (
    DiagnosisError,
    generate_diagnostic_draft,
)
from diagnostic_assist.diagnosis_models import DiagnosticDraft
from diagnostic_assist.models import EvidenceBundle
from diagnostic_assist.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class DiagnosticResult(BaseModel):
    status: Literal["draft_ready", "unavailable"]
    evidence: EvidenceBundle
    draft: DiagnosticDraft | None
    message: str | None

    @model_validator(mode="after")
    def validate_status(self) -> Self:
        if self.status == "draft_ready" and self.draft is None:
            raise ValueError("A ready result requires a draft.")

        if self.status == "unavailable" and self.draft is not None:
            raise ValueError("An unavailable result must not contain a draft.")

        return self


def prepare_diagnostic_result(
    evidence: EvidenceBundle,
    client: OllamaClient,
    *,
    asked_questions: Sequence[str] = (),
) -> DiagnosticResult:
    try:
        draft = generate_diagnostic_draft(
            evidence,
            client,
            asked_questions=asked_questions,
        )
    except DiagnosisError as exc:
        logger.warning("Diagnostic draft unavailable: %s", exc)

        return DiagnosticResult(
            status="unavailable",
            evidence=evidence,
            draft=None,
            message=(
                "Diagnostic suggestions are unavailable. "
                "You can still review the historical cases "
                "and continue preparing the service visit."
            ),
        )

    return DiagnosticResult(
        status="draft_ready",
        evidence=evidence,
        draft=draft,
        message=None,
    )