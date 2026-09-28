# ADR 0002: V1 canonical record scope is deliberately narrow

**Status:** Proposed

## Context

The long-term architecture includes concepts that are not yet specified or scheduled and would make V1 acceptance ambiguous.

## Decision

V1 requires `manifest`, `document`, `node`, `span`, `relation`, `attribute`, `preservation_record`, and `preservation_bundle`. Fidelity diagnostics are package metadata. `collection`, `asset`, full provenance and capability layers, and a cross-source identity ledger are deferred.

## Consequences

- V1 has a finite schema and test surface.
- Deferred concepts require separate product decisions before becoming requirements.
- The design may reserve their architectural roles without implying implementation.
