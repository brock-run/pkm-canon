# ADR 0017: Human approval is required before activation

**Status:** Proposed

## Context

Inferred conventions may be plausible but incorrect or inappropriate. V1 must not silently turn model output into active configuration.

## Decision

Rules begin as `proposed` and remain inactive until an authorized operator records a rule-level approval. Approval and rejection are immutable audit events with reviewer identity, timestamp, run ID, decision, and optional rationale.

## Consequences

- LangGraph pauses at an `awaiting_review` boundary.
- Rejected rules remain auditable but are excluded from active manifests.
- Approved manifests are immutable, versioned snapshots; a later review publishes a successor rather than mutating history.
- Repeated decision requests must be idempotent.
- Operator authentication and authorization are required before release.
