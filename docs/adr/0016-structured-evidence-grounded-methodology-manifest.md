# ADR 0016: Methodology output is structured and evidence-grounded

**Status:** Proposed

## Context

Free-form AI prose cannot be reliably validated, reviewed, compared, or activated as configuration.

## Decision

Convention detection emits a versioned, schema-validated methodology manifest. Each rule has a stable ID, typed category, statement, confidence, lifecycle status, and one or more `source_trace_ids` resolving to canonical nodes or spans.

## Consequences

- Methodology manifests require Pydantic models, JSON Schemas, and fixtures.
- Trace resolution and grounding are validation requirements, not prompt suggestions.
- Prompt, model, provider, run, and source-package identity are recorded for reproducibility.
