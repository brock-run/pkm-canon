# ADR 0003: Pydantic core models publish committed JSON Schema contracts

**Status:** Proposed

## Context

Runtime validation needs Python-native models, while packages, CI, and other consumers need portable schemas. Manually maintaining both core definitions invites drift.

## Decision

Pydantic models are the implementation source for V1 core records. JSON Schema Draft 2020-12 contracts are generated with `model_json_schema(by_alias=True)`, committed under `docs/specs/schemas/core/`, and reviewed. CI fails when regeneration changes committed output.

The manifest also has a committed schema. Hand-authored common and preservation schemas may retain reusable `$ref` structure, but parity fixtures must demonstrate agreement with runtime models.

## Consequences

- Schema generation must be deterministic and repository-relative.
- Model changes require regenerated contracts in the same change.
- Database constraints may consume committed schemas, but package validation remains authoritative.
