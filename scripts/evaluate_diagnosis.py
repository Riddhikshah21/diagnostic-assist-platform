"""Evaluate generation against a fixed, manually reviewed candidate set."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from pydantic import ValidationError
from diagnostic_assist.diagnosis import (
    DiagnosisError,
    generate_diagnostic_draft,
)
from diagnostic_assist.loader import load_cases
from diagnostic_assist.models import EvidenceBundle, EvidenceHit
from diagnostic_assist.ollama_client import OllamaClient


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument(
        "--queries",
        type=Path,
        default=Path("evaluation/diagnosis_queries.json"),
    )
    parser.add_argument("--query-id", default="D-001")
    parser.add_argument("--model", default="llama3.1:latest")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/results/diagnosis.json"),
    )
    args = parser.parse_args()

    cases_by_id = {
        case.case_id: case
        for case in load_cases(args.data)
    }

    definitions = json.loads(args.queries.read_text(encoding="utf-8"))
    matches = [
        definition
        for definition in definitions
        if definition["query_id"] == args.query_id
    ]
    if len(matches) != 1:
        raise ValueError("Query ID must identify exactly one evaluation case.")

    definition = matches[0]
    candidate_ids = definition["candidate_case_ids"]
    relevant_ids = set(definition["relevant_case_ids"])
    irrelevant_ids = set(definition["irrelevant_case_ids"])

    if not candidate_ids or len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("Candidate IDs must be nonempty and unique.")

    if relevant_ids & irrelevant_ids:
        raise ValueError("Relevant and irrelevant case IDs overlap.")

    if relevant_ids | irrelevant_ids != set(candidate_ids):
        raise ValueError("Every candidate must have a relevance judgment.")

    missing = set(candidate_ids) - cases_by_id.keys()
    if missing:
        raise ValueError(f"Cases absent from the data: {sorted(missing)}")

    for case_id in candidate_ids:
        if (
            cases_by_id[case_id].equipment_type
            != definition["equipment_type"]
        ):
            raise ValueError(f"Equipment type mismatch for {case_id}.")

    evidence = EvidenceBundle(
        query=definition["query"],
        equipment_type=definition["equipment_type"],
        hits=[
            EvidenceHit(
                case=cases_by_id[case_id],
                # Fixed evaluation candidates, not actual retrieval scores.
                rrf_score=0.0,
                source_ranks={},
                match_scope="equipment_type",
            )
            for case_id in candidate_ids
        ],
    )

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "query_id": args.query_id,
        "model": args.model,
        "input_mode": "fixed_evaluation_candidates",
        "evaluation_definition": definition,
        "manual_review": "pending",
    }

    try:
        draft = generate_diagnostic_draft(
            evidence,
            OllamaClient(model=args.model),
        )
    except DiagnosisError as exc:
        cause = exc.__cause__

        if isinstance(cause, ValidationError):
            details = cause.errors(
                include_input=False,
                include_context=False,
                include_url=False,
            )
        else:
            details = str(cause) if cause else str(exc)

        report.update(
            {
                "generation_status": "failed",
                "error": str(exc),
                "error_type": type(cause).__name__ if cause else None,
                "error_details": details,
                "draft": None,
            }
        )
        exit_code = 1
    else:
        cited_ids = {
            reference.case_id
            for cause in draft.possible_causes
            for reference in cause.evidence
        }
        irrelevant_citations = sorted(cited_ids & irrelevant_ids)

        report.update(
            {
                "generation_status": "validated",
                "citation_checks": {
                    "supplied_case_ids_and_exact_quotes": "passed",
                    "irrelevant_cases_cited": irrelevant_citations,
                },
                "draft": draft.model_dump(mode="json"),
            }
        )
        exit_code = 1 if irrelevant_citations else 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nReport saved to {args.output}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())