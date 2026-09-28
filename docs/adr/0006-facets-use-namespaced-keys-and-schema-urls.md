# ADR 0006: Facets use namespaced keys and schema URLs

**Status:** Proposed

## Context

Understood extensions need an evolution path that does not add every source- or adapter-specific field to the core model.

## Decision

Facet maps use stable namespaced keys. Each value is a `FacetEnvelope` that serializes required `_schemaURL`, optional-but-recommended `_producer`, and schema-defined payload fields.

Python uses safe internal names such as `schema_url` and `producer` with Pydantic aliases. Literal underscore-prefixed Python attributes are not the interchange contract.

## Consequences

- Facet payloads are discoverable and independently versioned.
- Facet serialization tests must use aliases.
- A facet without `_schemaURL` is invalid.
- Opaque source data still belongs in preservation artifacts.
