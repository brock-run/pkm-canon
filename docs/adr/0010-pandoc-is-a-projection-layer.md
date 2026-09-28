# ADR 0010: Pandoc is a downstream projection layer

**Status:** Proposed

## Context

Pandoc is effective for document rendering but cannot represent the full graph, identity, facet, and preservation semantics of the canonical package.

## Decision

Pandoc is used only to render document-oriented canonical subsets. V1's Pandoc output is an audit-oriented Markdown projection. It is neither the canonical model nor a full Obsidian or Logseq adapter contract.

## Consequences

- Canonical-to-Pandoc conversion is one-way and explicit.
- Unrepresentable constructs produce projection diagnostics.
- Target-specific round-trip adapters require separate contracts and capability notes.
