# ADR 0019: Adapter contracts are independently versioned

**Status:** Proposed

## Context

Source mapping logic and target projection capabilities change independently of the canonical package schema.

## Decision

Each source profile and target adapter has an independent semantic contract version. The manifest records `source_profiles[].profile_version` and the `adapter_contracts` map separately from `package_schema_version`.

Adapters document what they fully represent, approximate with diagnostics, preserve without normalization, or do not support. A machine-readable capability layer is deferred until multiple production adapters justify it.

## Consequences

- Parser and projector changes can be released without unnecessary package-version bumps.
- Fixtures are keyed to the applicable profile or adapter contract.
- Consumers must not infer round-trip fidelity from the presence of an adapter name alone.
