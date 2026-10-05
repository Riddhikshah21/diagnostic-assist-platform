import json
from typing import Any

import pytest

from diagnostic_assist.diagnosis_service import prepare_diagnostic_result
from diagnostic_assist.models import (
    EvidenceBundle,
    EvidenceHit,
    HistoricalCase,
)
from diagnostic_assist.ollama_client import OllamaClient, OllamaError


class StubOllamaClient(OllamaClient):
    """Return fixed responses or errors without making HTTP requests."""

    def __init__(self, responses: list[str | Exception]) -> None:
        super().__init__()
        self.responses = iter(responses)

    def generate(
        self,
        prompt: str,
        *,
        system: str = "",
        schema: dict[str, Any] | None = None,
    ) -> str:
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture
def evidence() -> EvidenceBundle:
    case = HistoricalCase(
        case_id="TEST-DIAG-001",
        equipment_family="Demo equipment",
        equipment_type="DEMO-100",
        created_at="2026-01-01T10:00:00Z",
        language="en",
        customer_description="The machine will not start.",
        technician_notes="Main contactor coil open.",
        parts_replaced=["DEMO-CONTACTOR"],
        resolution_text="Replaced main contactor.",
    )

    return EvidenceBundle(
        query="The machine will not start.",
        equipment_type="DEMO-100",
        hits=[
            EvidenceHit(
                case=case,
                rrf_score=0.03,
                source_ranks={"semantic": 1},
                match_scope="equipment_type",
            )
        ],
    )


def assessment_response() -> str:
    return json.dumps(
        {
            "category": "machine_problem",
            "reported_symptoms": ["The machine will not start."],
            "reason": "A machine malfunction is reported.",
        }
    )


def draft_response(quote: str) -> str:
    return json.dumps(
        {
            "summary": "The machine will not start.",
            "possible_causes": [
                {
                    "cause": "Main contactor failure",
                    "evidence": [
                        {
                            "case_id": "TEST-DIAG-001",
                            "field": "technician_notes",
                            "quote": quote,
                        }
                    ],
                }
            ],
            "follow_up_question": None,
            "limitations": ["An onsite diagnosis is still required."],
        }
    )


def test_generation_timeout_preserves_evidence(
    evidence: EvidenceBundle,
) -> None:
    client = StubOllamaClient(
        [
            assessment_response(),
            OllamaError("The local model timed out."),
        ]
    )

    result = prepare_diagnostic_result(evidence, client)

    assert result.status == "unavailable"
    assert result.draft is None
    assert result.evidence == evidence
    assert result.message is not None


def test_invalid_quote_returns_fallback(
    evidence: EvidenceBundle,
) -> None:
    client = StubOllamaClient(
        [
            assessment_response(),
            draft_response("Battery failed its load test."),
        ]
    )

    result = prepare_diagnostic_result(evidence, client)

    assert result.status == "unavailable"
    assert result.draft is None
    assert result.evidence == evidence


def test_valid_draft_is_returned(
    evidence: EvidenceBundle,
) -> None:
    client = StubOllamaClient(
        [
            assessment_response(),
            draft_response("Main contactor coil open."),
        ]
    )

    result = prepare_diagnostic_result(evidence, client)

    assert result.status == "draft_ready"
    assert result.draft is not None
    assert result.evidence == evidence
    assert result.message is None
    assert result.draft.possible_causes[0].explanation == (
        'Historical case TEST-DIAG-001: "Main contactor coil open."'
    )