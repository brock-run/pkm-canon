# ADR 0012: Normalization is deterministic and never silently drops data

**Status:** Proposed

## Context

Migration output must be replayable and its fidelity must be measurable. A promise of “perfect translation” is neither accurate nor testable for unsupported source features.

## Decision

Identical source bytes, parser version, source profile version, and configuration produce identical canonical IDs, records, ordering, preservation hashes, and diagnostic codes, excluding documented run metadata.

Every parsed source construct is fully normalized, partially normalized with preservation and diagnostics, preserved-only, unsupported with preservation, or rejected as invalid. Silent dropping is prohibited.

## Consequences

- Canonical output may not use random UUIDs or wall-clock fallbacks.
- The manifest carries reconciled fidelity summary counts.
- Fixture-based determinism and no-silent-loss tests are release gates.
