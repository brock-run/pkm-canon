# Implementation Plan and Work Breakdown: PKM Migrator V1

**Status:** Proposed
**Last updated:** 2026-09-28

## 1. Delivery order

V1 is built in this order:

1. align runtime models and portable contracts;
2. create deterministic Roam-to-package ingestion;
3. wrap ingestion in a job-oriented API;
4. load validated packages into PostgreSQL and build retrieval;
5. produce and review evidence-grounded methodology manifests;
6. add the audit-oriented Markdown projection.

Each work item is complete only when its acceptance criteria and listed tests pass. A filesystem package MUST validate before database loading begins.

## 2. Known starting-state gaps

These are confirmed repository issues, not future possibilities:

- Generated core schemas include `facets` on records whose current Pydantic models do not all expose `facets`.
- Core schemas do not currently enforce `additionalProperties: false`, despite the strict-core decision.
- The preservation schemas and Pydantic preservation models expose different fields.
- The schema generator writes to `specs/schemas/core/`, while the committed contracts live under `docs/specs/schemas/core/`.
- Committed schemas still use placeholder `https://example.org/...` identifiers, and `SourceNativeReference` does not yet enforce storage-kind-specific fields.
- No manifest, diagnostic, methodology-manifest, or review-event schema exists.
- The parser uses random UUIDs for several canonical IDs and current time for missing source timestamps, so output is not deterministic.
- The CLI writes record files but does not create or validate a complete manifest-backed package.

Workstream 0 resolves these gaps before new platform work depends on the contracts.

## 3. Workstream 0 — Canonical contract hardening

### WI-000: Align runtime models and serialized record contracts

- **Objective:** Make the Pydantic core models, preservation models, schemas, and ADRs describe the same fields and strictness.
- **Files:** `src/pkmcanon/models.py`, `docs/specs/schemas/core/`, `docs/specs/schemas/preservation/`, model and schema tests.
- **Approach:** Add typed `facets: dict[str, FacetEnvelope]` consistently to core records; use safe internal facet field names with aliases; set core models to reject extra fields; either add the documented preservation fields to runtime models or remove them from the contract through an explicit decision; enforce the required locator field for each `SourceNativeReference.storage_kind`.
- **Acceptance:** Positive and negative fixtures have the same validation outcome through Pydantic and JSON Schema; unknown core fields fail; facet aliases round-trip with `by_alias=True`; incomplete or contradictory storage descriptors fail.
- **Depends on:** none.

### WI-001: Fix repeatable schema generation and drift detection

- **Objective:** Generate reviewed core and manifest schemas into the actual committed contract directory.
- **Files:** `scripts/generate_schemas.py`, `docs/specs/schemas/core/`, CI configuration.
- **Approach:** Generate with `model_json_schema(by_alias=True)`; resolve paths relative to the repository rather than the process working directory; choose stable versioned schema identifiers; write deterministic JSON; add a check mode that fails on a diff.
- **Acceptance:** Running generation twice produces no diff; CI fails when a model change is not accompanied by regenerated schemas; no duplicate `specs/` tree is created at repository root; committed schemas contain no placeholder identifiers.
- **Depends on:** WI-000.

### WI-002: Define manifest, inventory, and fidelity diagnostics

- **Objective:** Make package completeness and no-silent-loss accounting machine-verifiable.
- **Files:** manifest/diagnostic models, new schemas under `docs/specs/schemas/`, example package.
- **Approach:** Add source hash, parser/profile metadata, file inventory, record counts, file hashes, and fidelity summaries to the manifest; define detailed diagnostic fields and stable codes.
- **Acceptance:** The example manifest validates; file inventory and fidelity totals reconcile with package contents; a partial normalization fixture has a resolvable diagnostic and preservation ID.
- **Depends on:** WI-000.

### WI-003: Complete the package validator

- **Objective:** Validate both record shapes and package-level invariants.
- **Files:** `src/pkmcanon/schema_validation.py`, `src/pkmcanon/package.py`, validation tests.
- **Approach:** Validate manifest and JSONL lines, `$ref` resolution, unique IDs, references, parent relationships, record counts, hashes, blob paths, and diagnostic reconciliation. Do not fetch remote schemas or external URIs during validation.
- **Acceptance:** The valid example passes; fixtures with duplicate IDs, dangling references, bad hashes, traversal paths, or mismatched counts fail with stable error codes.
- **Depends on:** WI-001, WI-002.

### WI-004: Complete developer CLI entry points

- **Objective:** Provide local and CI entry points before the API layer.
- **Files:** `src/pkmcanon/cli.py`, `pyproject.toml`.
- **Approach:** Add `generate-schemas`, `validate`, and `ingest-roam` commands with non-zero failure exits and structured summaries.
- **Acceptance:** A clean checkout can generate/check schemas, validate the example, and ingest a fixture into a complete package through documented commands.
- **Depends on:** WI-001, WI-003.

## 4. Workstream 1 — Deterministic Roam package ingestion

### WI-005: Specify deterministic IDs and Roam source profile

- **Objective:** Define replay-stable identity and mapping behavior before expanding the parser.
- **Files:** Roam source-profile documentation, parser utilities, fixtures.
- **Approach:** Preserve page/block UIDs; define namespace and escaping rules; derive IDs for spans, relations, attributes, preservation artifacts, and diagnostics from source identity plus deterministic discriminators; define behavior for missing UIDs and timestamps.
- **Acceptance:** The specification includes examples and collision behavior; randomized UUIDs and wall-clock substitution are absent from canonical output paths.
- **Depends on:** WI-002.

### WI-006: Implement Roam parser and package writer

- **Objective:** Convert Roam exports into a complete canonical package.
- **Files:** `src/pkmcanon/parsers/roam.py`, package writer, parser fixtures and tests.
- **Approach:** Map pages to documents; block trees to nodes; rich text to spans; references, embeds, and tags to relations; attributes to attribute records; unsupported macros and source-native data to preservation artifacts; all partial outcomes to diagnostics. Preserve the source export by content hash according to retention configuration.
- **Acceptance:** Supported fixtures produce all applicable record families, a valid manifest, stable order, and zero unaccounted source objects.
- **Depends on:** WI-003, WI-005.

### WI-007: Add determinism and fidelity regression suites

- **Objective:** Prevent parser changes from changing identity or losing source constructs silently.
- **Files:** parser tests and a representative Roam fixture corpus.
- **Approach:** Run the same input twice in isolated directories and compare canonical records, ordering, hashes, and diagnostics after excluding documented run metadata. Include nested blocks, missing UIDs, attributes, tags, page/block refs, embeds, queries, macros, and malformed input.
- **Acceptance:** Determinism tests pass; every fixture's source-object counts reconcile with fidelity summaries; malformed input produces stable errors.
- **Depends on:** WI-006.

## 5. Workstream 2 — API and job lifecycle

### WI-008: Implement ingestion transport and durable jobs

- **Objective:** Expose package ingestion without coupling it to request duration.
- **Files:** `src/api/main.py`, `src/api/ingest.py`, job models/storage.
- **Approach:** Stream uploads, enforce configured limits, hash while writing, deduplicate by source hash plus profile/config, return `202` and `job_id`, and implement the specified job states and stable failure responses.
- **Acceptance:** Valid uploads reach `package_ready`; malformed or oversized uploads fail safely; retries do not publish duplicate packages; status responses expose current state and retryability.
- **Depends on:** WI-007.

### WI-009: Secure package publication and retention

- **Objective:** Prevent partial publication and unsafe file handling.
- **Files:** package storage module and security tests.
- **Approach:** Use staging directories and atomic finalization; validate relative paths; reject archive traversal; configure raw-export/blob retention and cleanup; avoid following untrusted external URIs.
- **Acceptance:** Interrupted writes never appear complete; traversal fixtures fail; retention behavior is configuration-tested.
- **Depends on:** WI-006.

## 6. Workstream 3 — Operational database and retrieval

### WI-010: Create relational projection and migrations

- **Objective:** Load validated packages into a queryable, rebuildable PostgreSQL projection.
- **Files:** `alembic.ini`, `alembic/env.py`, migrations, loader modules.
- **Approach:** Create tables for packages, documents, nodes, spans, relations, attributes, preservation artifacts, diagnostics, jobs, and load state. Preserve canonical IDs and package identity. Use Expand-Migrate-Contract for later destructive changes.
- **Acceptance:** Upgrade/downgrade tests pass; loading the same package twice is idempotent; the projection can be rebuilt from package files.
- **Depends on:** WI-003.

### WI-011: Add bounded JSONB constraints

- **Objective:** Enforce useful database invariants without making the database a second canonical validator.
- **Files:** database migrations and constraint integration tests.
- **Approach:** Apply schema-backed constraints to selected facets or preservation payloads only after deployment support for the chosen extension is verified. Pin the extension and behavior in deployment documentation.
- **Acceptance:** Invalid constrained payloads fail; valid committed fixtures load; package validation remains independently runnable.
- **Depends on:** WI-001, WI-010.

### WI-012: Implement retrieval-unit assembly and embeddings

- **Objective:** Produce traceable retrieval units from canonical content.
- **Files:** chunking, embedding, and DB modules.
- **Approach:** Define stable chunk boundaries; retain node/span evidence IDs; store generated context separately; configure embedding provider, model, and dimension; validate stored vector dimension against configuration.
- **Acceptance:** Every retrieval unit resolves to canonical evidence; embedding retries are idempotent; changing configured dimensions requires an explicit migration/reindex path.
- **Depends on:** WI-010.

### WI-013: Implement and evaluate hybrid retrieval

- **Objective:** Support lexical and vector evidence retrieval for inference.
- **Files:** retrieval modules, indexes, labeled evaluation fixtures.
- **Approach:** Implement both paths and a configurable fusion strategy. Add reranking only if evaluation demonstrates value.
- **Acceptance:** Both paths return resolvable evidence and meet documented baseline metrics on the labeled corpus; latency and recall are recorded, not assumed.
- **Depends on:** WI-012.

## 7. Workstream 4 — Convention detection and review

### WI-014: Define methodology manifest and review schemas

- **Objective:** Establish the output contract before prompting an LLM.
- **Files:** Pydantic models and schemas for methodology manifests, rules, and review events.
- **Approach:** Define rule IDs, categories, statements, confidence semantics, trace IDs, lifecycle status, manifest/run identity, and review audit fields.
- **Acceptance:** Positive/negative fixtures validate; every trace ID is checked against its source package; invalid lifecycle transitions fail.
- **Depends on:** WI-003.

### WI-015: Configure durable LangGraph state

- **Objective:** Persist inference and review pauses without cross-run contamination.
- **Files:** `src/ai/graph_state.py`, checkpoint configuration and tests.
- **Approach:** Key checkpoints by run and package identity; store prompt/model/provider versions; pause at `awaiting_review`; make node execution retry-safe.
- **Acceptance:** A forced process termination resumes from the intended node with no duplicated decisions or cross-run state.
- **Depends on:** WI-010, WI-014.

### WI-016: Implement grounded rule inference

- **Objective:** Generate schema-bound proposed rules from retrieved evidence.
- **Files:** agent nodes, prompts, provider adapters, evaluation tests.
- **Approach:** Require structured output; validate trace IDs and quotations/claims against retrieved records; reject or retry ungrounded output; keep provider selection configurable.
- **Acceptance:** Every emitted rule validates and has resolvable evidence; deliberately ungrounded fixture output is rejected; prompt/provider/model versions are recorded.
- **Depends on:** WI-013, WI-014, WI-015.

### WI-017: Implement operator review and active-manifest publication

- **Objective:** Ensure no proposed rule becomes active without an auditable decision.
- **Files:** review API endpoints, authorization, decision store, publication service.
- **Approach:** Fetch pending rules and evidence; authorize reviewers; accept rule-level approve/reject decisions; append immutable review events; publish a versioned active manifest containing approved rules only.
- **Acceptance:** Unauthorized decisions fail; approval metadata is complete; rejected rules remain auditable but inactive; replaying a request is idempotent.
- **Depends on:** WI-014, WI-015, WI-016.

## 8. Workstream 5 — Projection and operations

### WI-018: Implement audit-oriented Markdown projection

- **Objective:** Render supported canonical document content for human audit.
- **Files:** `src/adapters/pandoc.py`, adapter contract/capability note, fixtures.
- **Approach:** Build an explicit canonical-to-Pandoc intermediate representation; render supported spans and links; emit projection diagnostics for unsupported constructs.
- **Acceptance:** Fixture packages produce readable Markdown; output is deterministic; unsupported content is diagnosed rather than silently discarded; documentation avoids round-trip claims.
- **Depends on:** WI-003, WI-006.

### WI-019: Add provider-neutral telemetry and cost controls

- **Objective:** Observe reliability, fidelity, retrieval, inference, review, and spend without embedding a provider in the product contract.
- **Files:** telemetry interfaces, provider adapters, deployment configuration.
- **Approach:** Record stage timings, counts, validation failures, retrieval metrics, model usage/cost when available, and review outcomes. Configure budgets and notification sinks per deployment. Apply redaction and access controls.
- **Acceptance:** Tests cover providers with and without usage APIs; budget breaches emit a configured event; sensitive fixture text is absent from default logs.
- **Depends on:** WI-008, WI-013, WI-016.

## 9. Workstream 6 — Release operations and end-to-end acceptance

### WI-020: Establish deployable configuration, access control, and recovery

- **Objective:** Make the V1 service safe and operable outside a developer workstation.
- **Files:** deployment configuration, environment example, authentication/authorization modules, CI workflow, and operations runbook.
- **Approach:** Define configuration for package storage, database, provider adapters, retention, budgets, and secrets; authenticate callers; authorize ingestion and review actions; provide health/readiness checks; document database migration, backup, and restore procedures. The release environment MUST run Python 3.11+ and install the declared test dependencies reproducibly.
- **Acceptance:** A clean production-like environment starts from documented configuration; unauthenticated or unauthorized ingestion/review requests fail; an authorized operator can complete the workflow; a restore drill recovers a package and its review history; CI runs on the supported Python version.
- **Depends on:** WI-008, WI-010, WI-017.

### WI-021: Run an end-to-end V1 release candidate and evaluation

- **Objective:** Prove the product outcome, not merely individual components.
- **Files:** sanitized fixture corpus, labeled evaluation set, end-to-end tests, release checklist, and operator runbook.
- **Approach:** Exercise upload through package publication, database load, retrieval, inference, review, active-manifest publication, replay, and Markdown projection. Include expected failures and retry paths. Establish written acceptance thresholds for retrieval quality, rule usefulness/grounding, stage timing, and fidelity diagnostics before the release candidate is judged.
- **Acceptance:** The end-to-end suite passes on a sanitized representative corpus; every published rule has valid evidence and approval history; package replay is deterministic; recovery and authorization tests pass; the agreed evaluation thresholds and operator sign-off are recorded in the release checklist.
- **Depends on:** WI-018, WI-019, WI-020.

## 10. CI quality gates

Before V1 release, CI MUST run:

- schema generation drift detection;
- runtime-model versus JSON-Schema parity fixtures;
- positive and negative package validation fixtures;
- parser determinism and fidelity reconciliation tests;
- database migration and idempotent load tests;
- methodology trace-integrity and lifecycle tests;
- projection determinism and diagnostic tests;
- security fixtures for path traversal, oversized input, and external URI behavior.

## 11. Owner decisions required before the V1 release candidate

The plan now covers the required implementation work, but these product and deployment decisions need an explicit owner decision before WI-020/WI-021 can close:

- **Activation meaning:** Specify the consumer of an approved manifest. In V1, activation publishes a reviewed manifest; it does not automatically alter an external PKM or platform configuration.
- **Operator authorization:** Define who may ingest private exports, view preserved payloads, and approve rules, along with the identity provider or local access model.
- **Data boundary and retention:** Set storage location, encryption, backups, retention duration, and deletion workflow for raw exports, preserved blobs, prompts, and review history.
- **Provider boundary:** Select deployment providers and state whether private source text may leave the controlled environment for embeddings or inference.
- **Release measurements:** Approve a representative sanitized corpus and concrete thresholds for retrieval quality, grounded-rule usefulness, throughput, and recovery time.
- **Projection expectation:** Confirm that V1's Markdown output is for audit, not a guaranteed round-trip import into Obsidian or Logseq.

## 12. Explicitly deferred work

Do not silently pull these into V1 work items: cross-source identity resolution, full provenance/capability layers, additional source adapters, full target-specific round trips, real-time sync, end-user chat, or automatic rule application. Each requires a separate product decision and scheduled workstream.
