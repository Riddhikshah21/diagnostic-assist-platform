# Diagnostic Assist Platform

Diagnostic Assist is a conversational application for field-service teams. It helps dispatchers understand reported machine problems, find relevant historical cases and prepare a useful handoff for technicians.

The application combines multilingual hybrid retrieval with evidence-based diagnostic assistance. Every suggested cause should link to the historical evidence behind it.

**Status:** Under active development. The current implementation provides retrieval through a Python CLI. The backend API, web interface and diagnostic workflow are planned.

This project builds on the [original Diagnostic Assist prototype](https://github.com/Riddhikshah21/diagnostic-assist).

## Problem

Service teams collect valuable repair information, but much of it is stored as unstructured text.

Customer descriptions may be vague or multilingual. Technician notes may contain abbreviations, incomplete observations or conflicting findings. Historical cases do not have a consistent symptom taxonomy or root-cause field.

Diagnostic Assist aims to help teams use this information to prepare service visits and improve the chance of fixing a problem on the first visit.

## Product workflow

The main user is a service dispatcher speaking with a customer.

1. Select the equipment and enter the reported problem.
2. Review the assistant's understanding and correct missing or inaccurate details.
3. See relevant historical cases and possible causes with supporting evidence.
4. Answer a short follow-up question when it could help narrow the issue.
5. Review and edit the technician handoff.
6. Record the confirmed outcome after the visit.

The customer can answer `Unknown`. Missing information should remain unknown.

Checks requiring tools or technical expertise are left for the technician. The dispatcher can prepare a handoff at any point.

## Architecture

The intended application has four main parts:

| Component | Responsibility |
|---|---|
| React + TypeScript frontend | Case workspace, conversation, evidence and handoff |
| Python backend | API, session management and diagnostic orchestration |
| Retrieval service | Equipment-aware keyword and multilingual semantic search |
| Ingestion worker | Validation, embedding generation and index updates |

Persistent storage, search infrastructure and AWS deployment will be added as the implementation develops.

## Features and implementation status

| Feature | Status |
|---|---|
| Historical case validation | Implemented |
| BM25 keyword retrieval | Implemented |
| Multilingual semantic retrieval | Implemented |
| Weighted Reciprocal Rank Fusion | Implemented |
| Equipment-type filtering | Implemented |
| Equipment-family fallback based on result count | Implemented |
| Structured evidence output | Implemented |
| Unit tests and exploratory retrieval evaluation | Implemented |
| Persistent indexes and incremental ingestion | Planned |
| Relevance assessment and reranking | Planned |
| FastAPI backend | Planned |
| React + TypeScript interface | Planned |
| Conversation state and follow-up questions | Planned |
| Cited cause suggestions and editable handoffs | Planned |
| Outcome review and calibrated probabilities | Planned |
| Authentication and tenant isolation | Planned |
| Monitoring and AWS deployment | Planned |

## Retrieval approach

The current implementation searches historical customer descriptions using:

- **BM25** for technical terms and error codes.
- **Multilingual embeddings** for descriptions with similar meaning.
- **Weighted Reciprocal Rank Fusion** to combine the result lists.

It searches the selected equipment type first. If fewer than the requested number of results are available, it adds cases from other types in the equipment family.

Technician notes, resolutions and replaced parts are returned as historical outcome evidence. They are not included in the current search index.

The next retrieval improvements will separate candidate depth from display size, assess relevance and allow the system to report insufficient evidence.

## Diagnostic probabilities

Retrieval scores are not diagnostic probabilities.

The current application returns historical evidence without probability estimates. Reliable percentages require reviewed outcomes, a defined prediction target and calibration on held-out data.

Generated cause annotations will be stored separately from source records and treated as unverified until reviewed.

## Technology

### Current implementation

| Area | Technology |
|---|---|
| Language | Python 3.11+ |
| Validation | Pydantic |
| Numerical processing | NumPy |
| Keyword retrieval | rank-bm25 |
| Semantic retrieval | sentence-transformers |
| Testing | pytest |

Embedding model:

```text
sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

Current fusion settings:

- BM25 weight: `1.0`
- Semantic weight: `2.0`
- Candidate depth: requested result limit

These settings came from a small exploratory evaluation and are not production-tuned.

### Planned application stack

- FastAPI backend
- React + TypeScript frontend
- Persistent case storage and search indexes
- Background ingestion workers
- AWS deployment

Infrastructure decisions will be documented with their operational and cost tradeoffs before implementation.

## Getting started

### Prerequisites

- Python 3.11 or newer
- Git
- The supplied `sample_cases.json` file

### Installation

```bash
git clone https://github.com/Riddhikshah21/diagnostic-assist-platform.git
cd diagnostic-assist-platform

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### Sample data

```bash
mkdir -p data
```

Place the supplied file at:

```text
data/sample_cases.json
```

The sample data is not included in the repository. The current tests and evaluation scripts require it.

### Run a search

```bash
diagnostic-assist \
  --data data/sample_cases.json \
  --equipment-type CX-450 \
  --equipment-family "Air Compressor CX" \
  --query "Customer says the unit is completely dead" \
  --limit 5
```

The first run downloads the embedding model. Each invocation currently loads the model and builds the in-memory indexes.

The JSON response contains matching cases, source ranks, RRF scores, match scope and warnings.

## Testing and evaluation

Run the unit tests:

```bash
python -m pytest
```

Run the real-model retrieval evaluation:

```bash
python scripts/evaluate_retrieval.py
```

Compare fusion configurations:

```bash
python scripts/tune_fusion.py
```

Unit tests use a deterministic test embedder. The evaluation scripts use the real multilingual model against four manually selected sample queries.

When a historical case is used as a simulated new query, its own ID is excluded from retrieval.

These checks provide a starting point. They do not establish diagnostic accuracy or large-scale performance.

## Repository structure

```text
diagnostic-assist-platform/
├── docs/
├── scripts/
│   ├── evaluate_retrieval.py
│   └── tune_fusion.py
├── src/
│   └── diagnostic_assist/
│       ├── cli.py
│       ├── loader.py
│       ├── models.py
│       └── retrieval.py
├── tests/
├── pyproject.toml
└── README.md
```

The documents in `docs/` currently describe the original prototype and proposed architecture. They will be updated alongside the application.

## Development roadmap

1. Establish reproducible multilingual and negative-query evaluation.
2. Improve relevance handling, reranking and equipment-family fallback.
3. Add persistent ingestion and search.
4. Expose retrieval and case sessions through an API.
5. Build the dispatcher interface.
6. Add grounded cause suggestions, follow-ups and handoffs.
7. Collect reviewed outcomes and evaluate probability calibration.
8. Add security, monitoring, load testing and deployment.

## Production acceptance goals

Before treating the application as production-ready, we will verify:

- Retrieval quality across supported languages and equipment groups.
- Appropriate behaviour when evidence is weak or contradictory.
- Traceable evidence for diagnostic suggestions.
- First useful output within three seconds at p95 under defined load.
- Reliable ingestion of approximately 500 daily case updates.
- Performance with at least 100,000 historical cases.
- Authentication, tenant isolation and auditability.
- Recovery from failed jobs and index updates.

Synthetic data can support load testing. Diagnostic quality requires realistic cases and reviewed outcomes.

## Current limitations

- The sample contains only 22 cases.
- Irrelevant cases can appear in the results.
- Family fallback uses result count rather than relevance.
- Indexes and embeddings are rebuilt for each CLI invocation.
- The API, frontend and diagnostic workflow are not implemented.
- No calibrated diagnostic probabilities are available.
- The latency and dataset-scale targets have not been verified.