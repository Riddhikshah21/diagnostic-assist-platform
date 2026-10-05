"""Compare retrieved case descriptions using a multilingual reranker."""

import argparse
from uuid import UUID

import httpx
from sentence_transformers import CrossEncoder


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", required=True, type=UUID)
    parser.add_argument("--query", default=None)
    args = parser.parse_args()

    response = httpx.get(
        f"http://127.0.0.1:8000/sessions/{args.session_id}/evidence",
        timeout=60.0,
        trust_env=False,
    )
    response.raise_for_status()
    evidence = response.json()["evidence"]
    hits = evidence["hits"]

    if not hits:
        print("No cases to rerank.")
        return

    model = CrossEncoder(
        "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
        device="cpu",
        trust_remote_code=False,
    )

    query = args.query or evidence["query"]

    pairs = [
        (query, hit["case"]["customer_description"])
        for hit in hits
    ]
    scores = model.predict(pairs, show_progress_bar=False)

    ranked = sorted(
        zip(hits, scores),
        key=lambda item: float(item[1]),
        reverse=True,
    )

    for rank, (hit, score) in enumerate(ranked, start=1):
        case = hit["case"]
        print(
            f"{rank}. {case['case_id']} | score={float(score):.4f}\n"
            f"   {case['customer_description']}"
        )


if __name__ == "__main__":
    main()