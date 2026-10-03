# Architecture and Technical Specification: PKM Migrator and Convention Detection Engine (V1)

**Status:** Proposed
**Last updated:** 2026-09-28

## 1. Purpose

V1 ingests a Roam Research JSON export, converts it into a validated canonical package, preserves source-native data that cannot be represented faithfully, and derives operational products from that package: a PostgreSQL projection, retrieval indexes, an evidence-grounded methodology manifest, and an audit-oriented Markdown projection.

The canonical package on disk is the authoritative result of ingestion. PostgreSQL, embeddings, AI outputs, and exports are reproducible derivatives, not alternate sources of truth.

Here “canonical” refers to Rosetta's **source representation canon**: a
validated record of what an identified source version contained. It does not
approve the source's factual assertions or promote generated outputs into a
domain or creative canon. See [ADR 0020](../adr/0020-canon-semantics-and-portable-contracts.md)
and the [portable contract design](canon-contracts-v0.1.md).

Every future activated methodology or export SHOULD carry an immutable
publication pin: source package/snapshot ID, exact evidence refs, retrieval
configuration and actual results, rule/prompt/model versions where used, and
review decisions. Source-to-record and evidence-to-output dependency edges
SHOULD be retained for reverse impact queries. Retrieval MUST apply source
access and requested context before ranking; a source record alone cannot
masquerade as an approved domain claim.

## 2. Document authority

- ADRs record durable architecture decisions and their consequences.
- This design specifies how those decisions fit together for V1.
- The PRD defines product behavior and acceptance outcomes.
- The implementation plan orders the work; it is not a separate product contract.
- Committed JSON Schemas define the serialized shape of records. A schema/model disagreement is a defect and must fail CI once the schema-drift check is in place.

`MUST`, `SHOULD`, and `MAY` are used normatively.

## 3. V1 boundaries

### 3.1 Required canonical artifacts

V1 packages contain these semantic record families:

- `manifest`
- `document`
- `node`
- `span`
- `relation`
- `attribute`
- `preservation_record`
- `preservation_bundle`

Fidelity diagnostics are package metadata rather than another semantic entity family. A package MUST include summary counts in its manifest and MUST include detailed diagnostics when normalization is partial, unsupported, or leaves an unresolved reference.

### 3.2 Deferred architecture

The following concepts have an architectural home but are not V1 acceptance requirements:

- `collection` and `asset` records
- a full W3C PROV-aligned provenance layer
- machine-readable capability negotiation beyond versioned adapter contracts
- a many-to-one, cross-source identity ledger
- bidirectional synchronization and source write-back
- production-grade Obsidian or Logseq round-trip adapters

V1 retains enough source identity and activity metadata to support replay and audit without prematurely designing these systems.

## 4. System shape

V1 is a Python pragmatic monolith.

| Concern | V1 choice |
| --- | --- |
| API | FastAPI |
| Runtime models | Pydantic |
| Portable validation | JSON Schema Draft 2020-12 |
| Canonical storage | Filesystem package: manifest, JSONL files, diagnostics, and blobs |
| Operational storage | PostgreSQL 14+ with `pgvector` |
| Durable inference workflow | LangGraph with PostgreSQL checkpoints |
| Developer interface | Typer CLI |
| Document projection | Pandoc as a downstream renderer |

A separate macro-orchestrator such as Prefect MAY be introduced later. It is not required for V1.

## 5. Canonical package contract

### 5.1 Layout

```text
<package-root>/
  manifest.json
  documents.jsonl
  nodes.jsonl
  spans.jsonl
  relations.jsonl
  attributes.jsonl
  preservation_records.jsonl
  preservation_bundles.jsonl
  diagnostics.jsonl          # required when detailed diagnostics exist
  blobs/                     # preserved source payloads and attachments
```

Record-family files use one JSON object per line. Empty files MAY be omitted only when the manifest inventory marks the family as empty. Blob references MUST be relative to the package root; path traversal outside the package is invalid.

The manifest MUST include at least:

- `package_id`
- `package_schema_version`
- `created_at`
- the source export content hash
- `source_profiles`
- `adapter_contracts`
- an inventory of package files with record counts and content hashes
- fidelity summary counts

The package is considered complete only after all declared files are written, hashes are computed, and package validation succeeds. Writers SHOULD use a staging directory and atomic finalization so partially written packages are never published as complete.

### 5.2 Version terminology

The following names have distinct scopes:

- `package_schema_version` versions the package layout and canonical record contract.
- `source_profiles[].profile_version` versions the mapping rules for a source system. A preservation artifact uses `source_profile_version` when it refers to the applicable profile directly.
- `adapter_contracts` maps an adapter name to that adapter's independent contract version.
- `schema_version` on a preservation artifact versions that artifact's record schema; it is not the package version.

Core JSONL records do not each repeat `package_schema_version`; the enclosing manifest supplies it.

### 5.3 Model and schema ownership

Pydantic models are the runtime implementation source for core records. Core schemas MUST be generated with `model_json_schema(by_alias=True)`, committed under `docs/specs/schemas/core/`, and reviewed like source code. The manifest also requires a committed schema.

Preservation and common schemas MAY retain hand-authored constraints and reusable `$ref` structure. CI MUST nevertheless prove that runtime models and committed schemas accept and reject the same fixture corpus.

Core records reject unknown top-level fields. Every core record MAY carry a `facets` map whose values are `FacetEnvelope` objects. `FacetEnvelope` is deliberately open for extension payload fields and serializes:

- `_schemaURL` — required, immutable schema identifier
- `_producer` — optional but recommended producer identifier

Python uses safe internal field names with aliases for these serialized names.

## 6. Normalization and fidelity

Normalization promises deterministic, explainable transformation—not perfect representation.

For every source construct, the parser MUST choose exactly one primary outcome:

1. fully normalized into canonical records;
2. partially normalized, with the lossy or unresolved part preserved and diagnosed;
3. preserved without normalization; or
4. rejected as invalid input, with a machine-readable error.

Silent dropping is forbidden. `unsupported` is a valid normalization status only when the source payload is preserved or the input itself is unavailable for a documented reason.

Detailed diagnostics use the term `diagnostics` consistently. Each diagnostic MUST include a stable code, severity, source locator, outcome, and related canonical or preservation IDs where available. The manifest summarizes at least:

- normalized source object count
- partially normalized count
- preserved-only count
- unsupported count
- unresolved-reference count
- warning and error counts

Given identical source bytes, parser version, source profile version, and normalization configuration, the parser MUST produce the same canonical IDs, record contents, record ordering, preservation hashes, and diagnostic codes. Run-specific fields such as package creation time and job ID are excluded from byte-for-byte determinism.

Source-backed IDs MUST derive from a documented source-scoped identity rule. Generated relations, attributes, spans, preservation artifacts, and diagnostics MUST derive from stable source identity plus a deterministic local discriminator; random UUIDs are not acceptable for canonical output.

## 7. Preservation model

`PreservationRecord` represents one preserved payload for a subject. `PreservationBundle` groups multiple payloads for the same source object, such as raw JSON plus rendered HTML. Both use `SourceNativeReference` for embedded content, package-relative blobs, or explicitly allowed external URIs.

Preservation artifacts MUST record the source system, subject, normalization status, and reason. They SHOULD record the source profile version, source locator, content type, byte length, and cryptographic hash whenever those values are knowable.

Opaque source payloads do not belong in core fields or untyped facets. Facets are for understood, schema-addressed extensions; preservation artifacts are for replayable source-native material.

## 8. Operational PostgreSQL projection

Only validated, complete packages may be loaded into PostgreSQL. The database stores:

- queryable canonical projections
- ingestion jobs and package load state
- embeddings and lexical indexes
- LangGraph checkpoints
- proposed methodology manifests and review events

Stable IDs, statuses, timestamps, and routing fields use relational columns. Sparse facets and bounded adjunct structures may use JSONB. Selected JSONB payloads MAY have JSON-Schema-backed database constraints, but package validation remains authoritative.

Database migrations use Alembic and Expand-Migrate-Contract where zero-downtime rollout is relevant. Package schema migrations use an ordered application-level registry keyed by `package_schema_version`. These version streams MUST NOT be conflated.

## 9. Retrieval and inference

Retrieval combines lexical search with dense embeddings. Fusion and reranking are implementation choices to be evaluated against a fixture corpus; no specific commercial reranker is a V1 requirement. Embedding provider, model, and vector dimension are deployment configuration and MUST NOT be hard-coded into the product contract.

Every retrieval unit MUST retain references to the canonical nodes and spans from which it was assembled. Added context, summaries, or chunk titles MUST be stored separately from source text so generated enrichment cannot be mistaken for canonical content.

LangGraph coordinates convention detection and durable review pauses. Inference produces a schema-validated methodology manifest rather than unconstrained prose. Each rule contains at least:

- `rule_id`
- `rule_type`
- `statement`
- `confidence`
- one or more `source_trace_ids`
- `status`: `proposed`, `approved`, or `rejected`

Each `source_trace_id` MUST resolve to a canonical `node_id` or `span_id`. Approval and rejection are separate audit events containing reviewer identity, timestamp, run ID, decision, and optional rationale. A proposed rule cannot become active without an approval event.

## 10. API and job lifecycle

The API accepts a streamed Roam JSON upload and returns `202 Accepted` with a `job_id`. The externally visible job states are:

`received` → `parsing` → `validating` → `package_ready` → `loading` → `indexing` → `inferring` → `awaiting_review` → `complete`

Any processing state may transition to `failed`. A failure response MUST include a stable error code and indicate whether the job is retryable. Approval or rejection resumes a job from `awaiting_review`; rejected rules never appear as active rules.

## 11. Projection strategy

Pandoc is a downstream rendering tool for document-oriented subsets. It cannot represent canonical graph identity, preservation payloads, all facets, or complete PKM link semantics. V1's Pandoc adapter is therefore an audit-oriented Markdown projection, not a claim of Obsidian or Logseq round-trip fidelity.

Every future target adapter requires its own versioned contract and documented capability limits even if Pandoc performs part of its rendering.

## 12. Provider and observability policy

LLM, embedding, reranking, telemetry, and cost providers are configurable adapters. Deployments MAY select Gemini, OpenAI, or other providers. Provider names, model names, dimensions, rate limits, spend ceilings, and notification destinations belong in deployment configuration.

Telemetry MUST cover job duration, record and diagnostic counts, validation failures, retrieval evidence, model/token usage when exposed by the provider, review outcomes, and cost estimates. Source content and prompts MUST be redacted or access-controlled; observability is not permission to copy private knowledge into an unrelated system.

## 13. Security and operational constraints

- Upload size and decompression limits MUST be configured and enforced.
- Package paths and archive entries MUST be checked for traversal.
- External URIs MUST NOT be fetched during validation unless an explicit policy permits it.
- Secrets MUST come from deployment configuration, never packages or committed fixtures.
- Raw exports, blobs, prompts, and evidence may contain sensitive data and MUST follow the deployment's retention and access policy.
- Package and database writes MUST be idempotent by package identity.

## 14. References to decisions

The ADR index in `docs/adr/README.md` is the authoritative list. Of particular importance are the decisions covering the canonical package, narrow V1 scope, deterministic normalization, PostgreSQL as a projection, structured AI output, human approval, and provider configurability.
