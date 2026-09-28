# ADR 0015: V1 uses source-scoped stable identity

**Status:** Proposed

## Context

V1 needs replay-stable IDs but does not yet have evidence or requirements for safely merging equivalent entities across independent knowledge graphs.

## Decision

V1 preserves source UIDs and derives canonical IDs within a documented source-system and source-graph namespace. Derived records use stable source identity plus deterministic local discriminators. A many-to-one cross-source identity ledger is deferred.

## Consequences

- Re-ingesting the same source does not create new canonical identities.
- Missing or duplicate source UIDs require explicit deterministic fallback and diagnostics.
- Cross-vault deduplication is a future, auditable workflow rather than hidden ingest behavior.
