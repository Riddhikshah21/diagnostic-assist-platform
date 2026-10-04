# Diagnostic Assist Platform — Implementation Plan

## Purpose

Build a complete local application that helps a service dispatcher understand a reported machine problem, find historical evidence, collect useful answers and prepare a technician handoff. After the visit, the technician's findings feed an outcome-review workflow.

The original assignment repository stays unchanged. Development belongs in `diagnostic-assist-platform`.

This is a proposed roadmap, not a description of completed functionality. We will update it as each phase is implemented and measured. No cloud service or paid inference API is required. Package and model downloads require connectivity during setup; runtime should use local services and downloaded models.

## Starting point

The reviewed prototype provides a Python CLI, Pydantic case validation, BM25 retrieval, multilingual embeddings, weighted Reciprocal Rank Fusion (RRF), equipment filtering and count-based family fallback. The reviewed baseline passed 18 unit tests using the supplied sample. It has no API, frontend, persistent index, conversation manager or diagnostic probability estimator.

Every CLI invocation builds the historical indexes again. Retrieval depth follows the display limit. Evaluation uses only four sample queries, and unit tests use a controlled embedder. These are the first limitations we will address.

## Target stack

| Layer | Proposed tools | Responsibility |
| --- | --- | --- |
| Frontend | React, TypeScript, Vite, CSS | Case workspace, conversation, evidence and handoff |
| API | Python, FastAPI, Uvicorn, Pydantic, HTTPX | Validated endpoints and workflow coordination |
| Application storage | PostgreSQL, SQLAlchemy, Alembic | Cases, sessions, annotations, jobs and feedback |
| Retrieval | OpenSearch, Python RRF | Keyword/vector candidate search and fusion |
| Models | sentence-transformers, local cross-encoder | Embeddings and reranking |
| Generation | Ollama and a locally licensed model | Cited suggestions, questions and summaries |
| Background work | Python worker and PostgreSQL job table | Import, embedding and indexing |
| Files | Local directories and persistent volumes | Original imports, exports and backups |
| Runtime | Podman with a tested Compose provider | Local service orchestration |
| Verification | pytest, Playwright, Ruff, ESLint, Locust | Tests, checks and load evaluation |
| Later probability work | scikit-learn | Modelling and calibration against reviewed outcomes |

The LLM and reranker are not selected yet. We will choose them after checking hardware, licences and multilingual benchmarks. PostgreSQL is the source of truth; OpenSearch is a rebuildable search projection. The API and worker share one Python package rather than starting as many independent services.

## Phase summary

| Phase | Deliverable | Depends on |
| --- | --- | --- |
| 1 | Reproducible baseline and evaluation | Existing code |
| 2 | Local services and database foundation | Phase 1 |
| 3 | Persistent case ingestion | Phase 2 |
| 4 | Evaluated hybrid retrieval | Phase 3 |
| 5 | Session API and progressive responses | Phase 4 |
| 6 | Complete dispatcher interface | Phase 5 |
| 7 | Grounded diagnostic conversation | Phases 4–6 |
| 8 | Outcome review and probability validation | Phase 7 and sufficient reviewed data |
| 9 | Security, recovery and scale validation | Full workflow |

Security, regression tests and outcome collection begin earlier than their final acceptance phases. Phases describe delivery milestones, not permission to defer those concerns.

## Phase 1 — Establish a reproducible baseline

**Goal:** Make the project easy to run and its retrieval quality measurable before changing behaviour.

Work:

- Add a small, shareable test fixture with documented provenance. Keep any assignment or private data outside Git unless redistribution is permitted.
- Make evaluation accept a data path and a separate relevance-judgment file.
- Separate configuration for retrieval depth, reranking depth, display limit and fusion weights.
- Reuse one fusion implementation in the application and evaluation scripts.
- Add queries in EN, DE, FR and IT, mixed-language descriptions, technical codes and abbreviations.
- Add unrelated queries, sparse equipment histories, contradictions and unknown equipment.
- Record baseline recall, precision, ranking quality and query timings. Define metric denominators explicitly.
- Separate tuning queries from held-out evaluation queries. Preserve query-case exclusion for historical simulations only.
- Pin dependencies and record model revisions; add lint and test commands.

Deliverables: reproducible setup, fixtures, evaluation configuration and baseline report.

**Completion:** A clean checkout runs the tests without a hidden sample-file dependency. Evaluation reports results by language and equipment group and records known failure cases. No production-quality claim comes from the 22-case sample alone.

## Phase 2 — Set up the local application foundation

**Goal:** Run the backend, database and search engine reliably on the development machine.

Work:

- Record available RAM, processor, disk and model acceleration before selecting runtime settings.
- Add a Compose configuration for PostgreSQL and OpenSearch with persistent volumes and health checks.
- Verify Podman and the chosen Compose provider on the Mac. Run Ollama natively if that is the better path for local acceleration.
- Add environment-based configuration and a safe `.env.example` without credentials.
- Create the FastAPI application skeleton and readiness/liveness endpoints.
- Add SQLAlchemy models and Alembic migrations.
- Introduce organisation ownership in records and API design now, even if the initial demo has one organisation.
- Bind internal services to appropriate local interfaces and use development credentials explicitly labelled as such.

Deliverables: local service configuration, database migrations and backend skeleton.

**Completion:** Documented commands start the services. Database and search data survive restarts. Readiness detects unavailable dependencies. The project does not require AWS or a hosted model.

## Phase 3 — Persist cases and build repeatable ingestion

**Goal:** Import historical data once, then handle additions and updates incrementally.

Work:

- Support JSON arrays initially and streaming JSONL for larger imports.
- Preserve source records and validate individual cases. Quarantine invalid records with actionable errors.
- Identify a case by organisation and source case ID. Store source version, content hash and import time.
- Upsert the authoritative case and its indexing job transactionally.
- Generate embeddings only when searchable content or the embedding revision changes.
- Index customer descriptions, vectors and filter metadata in batches.
- Make job claims, retries and index upserts duplicate-safe. Recover abandoned jobs using leases.
- Prevent an older worker job from overwriting a newer case version.
- Track import progress, indexed versions, failed jobs and deletion handling.
- Add an index rebuild command and a controlled index-version switch.

Deliverables: import CLI, worker, case storage, persistent search index and import report.

**Completion:** Reimporting identical data creates no duplicate cases or unnecessary embedding work. Updated cases are eventually searchable at the correct version. An interrupted import resumes without starting from zero. Failed records do not stop valid records.

## Phase 4 — Improve retrieval and weak-evidence handling

**Goal:** Return useful evidence rather than simply filling a result list.

Work:

- Add a retrieval interface so the current in-memory implementation remains a small-data reference.
- Query OpenSearch for BM25 and vectors using the same organisation and equipment constraints.
- Generate one query embedding and reuse it across scope searches.
- Fetch a candidate pool independently of the final display count, then deduplicate and apply weighted RRF.
- Benchmark a local multilingual cross-encoder for reranking. Preserve technical identifiers and negation examples in evaluation.
- Assess evidence relevance using development judgments. Treat any initial thresholds as provisional, not diagnostic probabilities.
- Broaden to compatible equipment in the family when type-specific evidence is insufficient, not only when fewer results exist.
- Rerank expanded candidates together and expose equipment scope and uncertainty.
- Return an explicit insufficient-evidence result when appropriate.

Deliverables: persistent retriever, reranker integration, relevance handling and comparison report.

**Completion:** Compare BM25, semantic-only, current fusion and reranked fusion on held-out queries. Inspect multilingual recall, irrelevant-result rates and fallback errors. Keep a simpler baseline if the added model does not justify its quality and latency costs.

## Phase 5 — Build the session API

**Goal:** Support a real case workflow through stable backend contracts.

Work:

- Add operations to create sessions, retrieve evidence, record answers, correct observations, save handoffs and record outcomes.
- Store known observations, unknown answers, assistant hypotheses and historical evidence separately.
- Version the session so concurrent or delayed responses cannot overwrite newer facts.
- Add structured error responses, request identifiers, timeouts and cancellation handling.
- Return initial evidence without waiting for generation. Add server-sent events for subsequent results.
- Store generated outputs with their session version, model revision and evidence references.
- Enforce organisation access at both record lookup and retrieval boundaries.

Deliverables: documented API schemas and integration tests.

**Completion:** API calls complete a case workflow, preserve corrections and reject unauthorised record access. A model failure still allows the client to receive retrieved evidence. Streaming never mixes results from different session versions.

## Phase 6 — Build the React + TypeScript workspace

**Goal:** Let a dispatcher complete the workflow without the CLI.

Work:

- Create the Vite application with case details, conversation and evidence areas.
- Add equipment selection, problem entry and confirmation/correction of known facts.
- Show historical evidence, visible match scope and original outcome text.
- Support answers, `Unknown`, corrections and incremental updates.
- Keep an editable handoff available even when the conversation cannot narrow the issue.
- Add loading, empty, error and disconnected states; handle stream reconnects without duplicating outputs.
- Provide accessible controls and a usable smaller-screen layout.
- Test the complete workflow through Playwright.

Deliverables: integrated browser application and end-to-end tests.

**Completion:** A dispatcher can create a session, inspect evidence, record answers and save a handoff. Browser refresh does not lose persisted work. The UI displays no invented diagnostic percentages.

## Phase 7 — Add grounded diagnostic assistance

**Goal:** Turn historical evidence into useful suggestions while keeping uncertainty visible.

Work:

- Compare local LLM candidates for EN/DE/FR/IT quality, memory use and latency. Record licences and model revisions.
- Pass structured observations and selected evidence to the model, including conflicting outcomes.
- Require structured causes, evidence references, excerpts, one proposed question and a draft handoff.
- Validate schema, referenced case IDs and cited excerpts. Treat historical text as untrusted input rather than instructions.
- Distinguish confirmed repair evidence, tentative notes, administrative cases and no-fault-found outcomes.
- Keep generated cause annotations separate from original records; do not silently turn them into verified labels.
- Select questions that distinguish competing causes and avoid repeating known or unknown answers.
- Restrict customer questions to the agreed workflow. Put technical measurements and invasive checks in the technician handoff.
- Fall back to evidence-only output when generation or validation fails.

Deliverables: local generation adapter, output validator, conversation policy and reviewed diagnostic examples.

**Completion:** Reviewers can trace suggestions to evidence. Unknown answers do not become negative evidence. Contradictions and unsupported claims are measured. Citation validity alone is not presented as proof of diagnostic correctness.

## Phase 8 — Collect outcomes and validate probabilities

**Goal:** Build an honest path to diagnostic probability estimates.

Outcome collection starts as soon as the workflow is available. Probability modelling waits until the data is suitable.

Work:

- Record confirmed findings, repair actions, parts, unresolved cases, repeat visits and outcome-review status.
- Define whether predictions refer to one primary cause or multiple causes; define the prediction time and handling of unseen causes.
- Create reviewed annotations separately from source records. AI can propose annotations but cannot approve them.
- Establish annotation guidance, disagreement review and dataset provenance.
- Split training, calibration and evaluation data without sharing future outcomes or duplicate incidents across splits.
- Train a baseline estimator and compare more complex approaches only when warranted.
- Measure Brier score, calibration, discrimination and performance by equipment volume and language. Report uncertainty on small groups.
- Version the estimator with its cause definitions and dataset. Define when the application abstains.

Deliverables: review workflow and dataset specification; model and calibration report only if evidence is sufficient.

**Completion:** Display percentages only when independent evaluation supports their interpretation. RRF normalization, similarity scores and retrieved case proportions are not substitutes. If suitable reviewed data is unavailable, keep evidence-based rankings and document this component as incomplete.

## Phase 9 — Validate security, scale and recovery

**Goal:** Demonstrate reliable local operation under a documented workload.

Work:

- Complete authentication, authorisation, organisation-isolation tests and audit records. Use secure credential handling and session management.
- Test 100,000 indexed cases and approximately 500 daily updates; distinguish synthetic load data from diagnostic evaluation data.
- Measure cold startup, warm requests, concurrent sessions, ingestion interference and model resource contention.
- Report time to first useful evidence separately from full diagnostic output. Test the three-second p95 target under a defined workload rather than assume it.
- Add structured metrics and logs without unnecessarily recording sensitive case text.
- Test model timeouts, unavailable search/database services, worker crashes and disk exhaustion behaviour.
- Verify database backup restoration and search-index reconstruction from authoritative records.
- Document dependency/model upgrades, schema migration, index rollback and operational limits.

Deliverables: load and failure report, backup/recovery runbook and reproducible local startup instructions.

**Completion:** State the tested hardware, concurrency, dataset and resource limits. Security and recovery checks pass. Unmet latency or diagnostic targets remain explicit limitations; an end-to-end demo alone does not establish production readiness.

## Milestones

| Milestone | What we can demonstrate |
| --- | --- |
| After Phase 1 | Reproducible, measurable retrieval baseline |
| After Phase 4 | Persistent retrieval with weak-evidence handling |
| After Phase 6 | End-to-end dispatcher workflow using historical evidence |
| After Phase 7 | Local conversational diagnostic assistance and handoff |
| After Phase 8 | Reviewed feedback loop; validated probabilities if data permits |
| After Phase 9 | Documented security, recovery and scale acceptance |

## Working rules

- Finish a small, reviewable phase before adding unrelated infrastructure.
- Test meaningful behaviour and preserve evaluation baselines.
- Record chosen parameters, evidence and tradeoffs in the repository.
- Keep runtime local and check framework and model licences.
- Keep private data and credentials out of Git.
- Use synthetic records for performance, not claims of diagnostic accuracy.
- Update README status and this plan when functionality changes.
- Do not promise delivery dates until hardware, dataset availability and phase scope are understood.

## Decisions needed before infrastructure setup

1. Mac processor, RAM and available disk space.
2. Whether realistic service data is available and what may be redistributed.
3. Initial number of concurrent users and whether the application stays on localhost or is shared on a local network.
4. Selected local LLM/reranker and their licences after benchmarking.

These decisions do not block Phase 1. The next implementation task is the baseline fixture, configurable evaluation and retrieval settings.
