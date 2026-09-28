# ADR 0009: Core records are strict and extensions are controlled

**Status:** Proposed

## Context

Arbitrary fields in core records make compatibility, validation, and migrations unpredictable. Some deliberate extensibility is still necessary.

## Decision

Core Pydantic models and JSON Schemas reject unknown top-level fields. Every supported core family may expose `facets: dict[str, FacetEnvelope]`. The facet envelope permits schema-addressed payload fields; preservation artifacts carry opaque source-native data.

## Consequences

- Pydantic `extra="forbid"` and JSON Schema `additionalProperties: false` must agree for core records.
- New core fields require normal schema governance.
- Untyped `dict[str, Any]` facets are not permitted.
