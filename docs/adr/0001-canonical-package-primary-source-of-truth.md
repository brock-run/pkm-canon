# ADR 0001: Canonical package is the primary source of truth

**Status:** Proposed

## Context

Normalization must remain portable, replayable, and auditable without requiring the operational database or an external service.

## Decision

The validated filesystem canonical package—`manifest.json`, JSONL record files, diagnostics, and preserved blobs—is the authoritative result of ingestion. PostgreSQL, indexes, embeddings, AI analyses, and exports are derived products. The manifest records a content-addressed hash of the source export and the package identifier.

An ingest publishes a package only after record, reference, inventory, count, path, and hash validation succeeds.

## Consequences

- Database projections can be rebuilt from packages.
- Re-embedding and re-analysis do not require source parsing.
- Package validation works offline.
- Atomic publication and content hashes become required implementation concerns.
