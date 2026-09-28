# ADR 0005: Core records share conventions but retain modular schemas

**Status:** Proposed

## Context

Record families need consistent identity and extension conventions without collapsing distinct semantics into a weak universal object.

## Decision

Core records share conceptual conventions—stable family-specific IDs, optional typed facets, and package-level version context—while each family retains a strict record-specific model and schema.

The common envelope is conceptual; V1 does not require an inheritance wrapper or a repeated schema-version field on every core record.

## Consequences

- Validators preserve strong record-family boundaries.
- Common behavior is tested across models without forcing identical fields.
- `package_schema_version` remains in the manifest rather than being duplicated on each core record.
