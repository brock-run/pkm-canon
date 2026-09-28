# ADR 0011: Source-native payloads remain outside core records

**Status:** Proposed

## Context

Raw source objects are necessary for loss prevention and replay but would destabilize core schemas if copied into normalized records.

## Decision

Opaque, unsupported, partially normalized, and replay-oriented source payloads are stored in preservation records or bundles. Core records contain only normalized semantics; facets contain understood schema-addressed extensions.

## Consequences

- Parsers cannot hide unresolved source blobs in core fields or untyped facets.
- Partial normalization links diagnostics, canonical subjects, and preservation artifacts.
- Preservation is a required fidelity mechanism, not best effort.
