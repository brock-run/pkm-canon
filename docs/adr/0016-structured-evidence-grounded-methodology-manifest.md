# ADR 0016: Methodology output is structured and evidence-grounded

**Status:** Proposed

## Context

Free-form AI prose cannot be reliably validated, reviewed, compared, or activated as configuration.

## Decision

Convention detection emits a versioned, schema-validated methodology manifest. Each rule has a stable ID, typed category, statement, confidence, lifecycle status, and one or more `source_trace_ids` resolving to canonical nodes or spans.

For `methodology-v2`, `confidence` is a **support heuristic**, not a calibrated
probability. It combines the share of substantive values (45%), distinct pages
with substantive values capped at five (40%), and substantive observations
capped at ten (10%). Blank values and obvious template placeholders contribute
no positive support. Repeated blocks on one page do not count as independent
pages. The proposal also records observation, distinct-page, substantive,
blank, and placeholder counts; case variants of one attribute key; and the
five most common keys co-occurring on those pages. Its Roam graph scope is
explicit. Candidates with fewer than two substantive values, or a majority of
blank/placeholder values, are deferred in the local review queue. Deferral
never changes source preservation or records an approval/rejection; a reviewer
must still make every decision. The v2 rule identity prevents old decisions
from silently admitting a changed proposal.

## Consequences

- Methodology manifests require Pydantic models, JSON Schemas, and fixtures.
- Trace resolution and grounding are validation requirements, not prompt suggestions.
- Prompt, model, provider, run, and source-package identity are recorded for reproducibility.
