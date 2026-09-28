# ADR 0013: PostgreSQL is an operational projection

**Status:** Proposed

## Context

The application needs query, vector, workflow, and review storage, but making that database canonical would couple portability and replay to infrastructure state.

## Decision

PostgreSQL stores a rebuildable projection of validated packages plus operational state: jobs, indexes, embeddings, checkpoints, methodology manifests, and review events. A package must validate before loading.

## Consequences

- Database loads are idempotent by package identity.
- Relational columns hold stable routing and lifecycle data; bounded sparse structures may use JSONB.
- Selected database constraints supplement but do not replace package validation.
- Backup policy must distinguish canonical packages from rebuildable projections and unique operational review state.
