# ADR 0008: Preservation bundles group multiple payloads per subject

**Status:** Proposed

## Context

One source object may require several related representations, such as raw JSON, rendered HTML, and an attachment.

## Decision

Use `PreservationRecord` for one payload and `PreservationBundle` when multiple `SourceNativeReference` items for one subject must travel together. A bundle declares its grouping strategy and may designate one valid primary item index.

## Consequences

- Related payloads remain explicitly grouped.
- Bundles must contain at least one item.
- Validators must check the primary index against the item count.
- Bundles do not replace canonical normalization where faithful normalization is possible.
