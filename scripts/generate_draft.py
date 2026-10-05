"""Manually test local diagnostic generation for a saved session."""

import argparse
import sys
from uuid import UUID

import httpx
from pydantic import ValidationError

from diagnostic_assist.diagnosis import (
    DiagnosisError,
    generate_diagnostic_draft,
)
from diagnostic_assist.ollama_client import OllamaClient
from diagnostic_assist.session_models import (
    SessionEvidenceResponse,
    SessionResponse,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", required=True, type=UUID)
    args = parser.parse_args()

    session_path = f"/sessions/{args.session_id}"

    try:
        with httpx.Client(
            base_url="http://127.0.0.1:8000",
            timeout=httpx.Timeout(60.0, connect=5.0),
            trust_env=False,
        ) as api:
            response = api.get(session_path)
            response.raise_for_status()
            session = SessionResponse.model_validate(response.json())

            response = api.get(f"{session_path}/evidence")
            response.raise_for_status()
            retrieved = SessionEvidenceResponse.model_validate(
                response.json()
            )

            if (
                retrieved.session_id != session.session_id
                or retrieved.revision != session.revision
            ):
                print(
                    "The session changed. Run the command again.",
                    file=sys.stderr,
                )
                return 1

            asked_questions = [
                observation.question
                for observation in session.observations
                if observation.question
            ]
            # Controlled experiment for this dead-panel example only.
            # This manually selected evidence must not become production filtering.
            # relevant_case_ids = {
            #     "C-48211",
            #     "C-48377",
            #     "C-48590",
            #     "C-49040",
            # }

            # controlled_evidence = retrieved.evidence.model_copy(
            #     update={
            #         "hits": [
            #             hit
            #             for hit in retrieved.evidence.hits
            #             if hit.case.case_id in relevant_case_ids
            #         ]
            #     }
            # )
            draft = generate_diagnostic_draft(
                retrieved.evidence,
                OllamaClient(),
                asked_questions=asked_questions,
            )

            response = api.get(session_path)
            response.raise_for_status()
            current = SessionResponse.model_validate(response.json())

            if current.revision != session.revision:
                print(
                    "The session changed during generation. "
                    "Run the command again.",
                    file=sys.stderr,
                )
                return 1

    except httpx.HTTPStatusError as exc:
        print(
            f"Backend returned HTTP {exc.response.status_code}. "
            "Check the session ID and backend logs.",
            file=sys.stderr,
        )
        return 1
    except httpx.RequestError:
        print(
            "Could not reach the backend, or the request timed out.",
            file=sys.stderr,
        )
        return 1
    except ValidationError:
        print("Backend returned invalid session data.", file=sys.stderr)
        return 1
    except DiagnosisError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(draft.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())