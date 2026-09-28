# PRD: PKM Migrator and Convention Detection Engine (V1)

**Status:** Proposed
**Last updated:** 2026-09-28

## 1. Product summary

V1 converts Roam Research JSON exports into portable, validated canonical packages without silently losing unsupported source constructs. It then loads those packages into an operational database, retrieves evidence, proposes a structured methodology manifest, and requires a human operator to approve or reject every rule before activation.

The product is a governed one-way ingestion and analysis system. It is not a live synchronization service.

## 2. Users

- **System operator:** submits exports, monitors jobs, investigates diagnostics, reviews evidence, and records decisions.
- **Knowledge owner:** expects source content and unsupported constructs to remain recoverable and attributable.

V1 does not include a knowledge-owner-facing conversational UI.

## 3. Goals

- Ingest Roam JSON through CLI and API entry points.
- Produce a complete, validated canonical package before any database load.
- Preserve unsupported or partially normalized source material with explicit fidelity accounting.
- Make ingestion replayable through deterministic IDs and stable record ordering.
- Produce evidence-grounded proposed methodology rules.
- Record auditable human approval or rejection before a rule becomes active.
- Provide an audit-oriented Markdown projection of supported document content.

## 4. Non-goals

- Bidirectional sync or write-back to Roam or another PKM tool.
- Full ingestion support for tools other than Roam.
- Automatic cross-vault entity merging.
- `collection` or `asset` canonical record families.
- A full provenance or capability-negotiation subsystem.
- A production-ready Obsidian or Logseq round-trip exporter.
- Automatic application of AI-proposed rules.

## 5. Product outcomes and success criteria

V1 is successful when all of the following hold:

| Outcome | Acceptance measure |
| --- | --- |
| Valid package | Every supported fixture produces a package that passes manifest, core, preservation, reference-integrity, inventory, and hash validation. |
| No silent loss | Every parsed source object is counted as normalized, partially normalized, preserved-only, unsupported, or rejected; all non-normalized outcomes have a diagnostic and preservation reference when source bytes are available. |
| Deterministic replay | Two runs with identical source bytes, parser version, source profile, and configuration produce identical canonical IDs, records, ordering, preservation hashes, and diagnostic codes, excluding documented run metadata. |
| Evidence grounding | 100% of proposed rules contain at least one `source_trace_id`, and every trace ID resolves to a canonical node or span in the source package. |
| Human governance | 0% of proposed rules become active without a recorded approval event containing reviewer identity, timestamp, run ID, and decision. |
| Regression safety | The fixture corpus, generated-schema drift check, and parser determinism test run in CI. |

Throughput and latency service-level objectives will be set after a representative corpus and deployment envelope exist. V1 MUST record stage timings and package sizes so those targets can be based on measurements rather than arbitrary limits.

## 6. User stories

- **US-001 — Ingestion:** As an operator, I can submit a Roam export and receive a job ID so I can track processing without keeping a request open.
- **US-002 — Fidelity:** As a knowledge owner, I can recover unsupported macros, queries, and source-native payloads so migration does not silently destroy them.
- **US-003 — Diagnosis:** As an operator, I can see what was fully normalized, partially normalized, preserved, unsupported, or unresolved so I can judge package quality.
- **US-004 — Traceability:** As an operator, I can open the exact canonical nodes or spans cited by a proposed rule so I can verify it.
- **US-005 — Governance:** As an operator, I can approve or reject rules individually and leave a rationale so downstream consumers receive only reviewed output.
- **US-006 — Replay:** As an operator, I can reload or re-analyze a validated package without repeating source parsing.

## 7. Functional requirements

### 7.1 Ingestion and canonicalization

- **REQ-001:** The system MUST accept a Roam JSON export from the CLI and from `POST /api/v1/ingest/roam`.
- **REQ-002:** The API MUST stream uploads, enforce configured size limits, calculate a cryptographic source hash, and return `202 Accepted` with a `job_id`.
- **REQ-003:** The parser MUST write a canonical filesystem package before the package is loaded into PostgreSQL.
- **REQ-004:** The package MUST contain the V1 artifact families and metadata defined in the design specification.
- **REQ-005:** The package MUST validate its records, cross-record references, file inventory, record counts, relative paths, and declared hashes before publication.
- **REQ-006:** Canonical IDs and record ordering MUST meet the deterministic replay measure in Section 5.
- **REQ-007:** Package schema, source profile, preservation schema, and adapter contract versions MUST use the distinct fields and scopes defined in the design specification.

### 7.2 Extensibility, preservation, and diagnostics

- **REQ-008:** Core records MUST reject unknown top-level fields and MAY extend through typed, namespaced facet envelopes.
- **REQ-009:** A facet MUST serialize `_schemaURL`; `_producer` is optional but SHOULD be supplied.
- **REQ-010:** Understood extension data MUST use facets. Opaque, unsupported, or replay-oriented source payloads MUST use preservation records or bundles.
- **REQ-011:** The parser MUST NOT silently drop a source object or construct.
- **REQ-012:** Partial, preserved-only, unsupported, and unresolved outcomes MUST emit detailed diagnostics with stable codes and source locators.
- **REQ-013:** The manifest MUST contain fidelity summary counts that reconcile with the detailed diagnostics and emitted records.

### 7.3 Operational loading and retrieval

- **REQ-014:** Only a complete, validated package may be loaded into PostgreSQL.
- **REQ-015:** A repeated load of the same package MUST be idempotent.
- **REQ-016:** Retrieval MUST support lexical and vector search and MUST retain canonical evidence IDs for every returned unit.
- **REQ-017:** Generated summaries or contextual enrichment MUST remain distinguishable from canonical source text.

### 7.4 Convention detection and governance

- **REQ-018:** The inference workflow MUST be durable and resumable across process interruption.
- **REQ-019:** Inference MUST produce a schema-validated methodology manifest, not free-form output.
- **REQ-020:** Every proposed rule MUST include `rule_id`, `rule_type`, `statement`, `confidence`, `status`, and one or more resolvable `source_trace_ids`.
- **REQ-021:** A proposed rule MUST remain inactive until an authorized operator records an approval.
- **REQ-022:** Approval and rejection events MUST record reviewer identity, timestamp, run ID, decision, and optional rationale.
- **REQ-023:** Rejected rules MUST remain available for audit but MUST NOT appear in the active manifest.

### 7.5 Projection

- **REQ-024:** V1 MUST provide a Markdown projection for supported document, node, span, and relation content.
- **REQ-025:** Projection diagnostics MUST identify constructs that cannot be rendered faithfully.
- **REQ-026:** The Markdown projection MUST NOT be described as a full Obsidian or Logseq round-trip contract.

## 8. Operator flow

1. The operator submits a Roam JSON export.
2. The service returns a `job_id` in state `received`.
3. The service parses, preserves, diagnoses, and validates a staged package.
4. On success, the service atomically publishes the package and enters `package_ready`.
5. The service loads the package, builds retrieval indexes, and runs convention detection.
6. The job enters `awaiting_review` with proposed evidence-linked rules.
7. The operator reviews the cited nodes or spans and approves or rejects each rule.
8. The service records immutable review events and publishes the active manifest containing approved rules.
9. The job enters `complete`. Any failed stage enters `failed` with a stable error code and retryability indicator.

## 9. Non-functional requirements

- **NFR-001 — Privacy and security:** Uploads, blobs, prompts, and evidence MUST follow configured retention, access, and redaction policies. Package paths and archive entries MUST be traversal-safe.
- **NFR-002 — Portability:** A canonical package MUST be independently validatable without PostgreSQL, an LLM provider, or network access.
- **NFR-003 — Reliability:** Package publication and package loading MUST be idempotent and safe to retry.
- **NFR-004 — Observability:** The system MUST expose stage duration, counts, diagnostic summaries, validation failures, retrieval evidence, model usage when available, review outcomes, and estimated provider cost.
- **NFR-005 — Provider configuration:** LLM, embedding, telemetry, alerting, and cost integrations MUST be configurable; no named provider API is a product requirement.
- **NFR-006 — Schema governance:** CI MUST detect committed-schema drift and validate both positive and negative fixtures.
- **NFR-007 — Database integrity:** Stable relational invariants MUST use database constraints. Selected bounded JSONB payloads SHOULD use schema-backed constraints when operationally practical; database validation does not replace package validation.

## 10. Required product contracts still to be authored

The following are required V1 deliverables and are scheduled in the implementation plan:

- manifest JSON Schema, including inventory and fidelity summary
- detailed diagnostic schema and stable diagnostic-code catalog
- methodology manifest and review-event schemas
- deterministic ID specification for the Roam source profile
- adapter capability note for the V1 Markdown projection
- data retention and operator authorization configuration contract
