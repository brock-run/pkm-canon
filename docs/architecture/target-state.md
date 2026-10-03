# PKM Canon architecture: target state

**Status:** proposed direction, not implemented end to end. [Current implementation](current-state.md) and the [component map](component-map.md) identify what exists. The target preserves product-owned authority and keeps indexes rebuildable.

```mermaid
flowchart LR
  PC00["PC00 Source instances<br>Roam, Obsidian, Notion, Tana, others"] --> PC01["PC01 Versioned adapters and source profiles"]
  PC01 --> PC02["PC02 Immutable source package"]
  PC02 --> PC03["PC03 Fidelity and loss diagnostics"]
  PC03 --> PC04["PC04 Evidence-linked methodology and claim proposals"]
  PC04 --> PC08["PC08 Per-instance review workbench"]
  PC08 --> PC05["PC05 Authorized decision ledger and activation"]
  PC02 --> PC06["PC06 Rebuildable retrieval and audit projections"]
  PC02 --> PC07["PC07 Versioned source-neutral exchange"]
  PC05 --> PC06
```

`PC08` combines automated source-instance observations with human approval or rejection of proposed methodology. A source-type profile supplies defaults, while each import records its own scope, evidence, diagnostics, decisions, and versioned active manifest. Approval of a methodology rule does not endorse every assertion in the source. Adding adapters must not weaken package validation or silently discard native structure.

`PC07` remains a contract boundary to other products. Shared schemas and synthetic fixtures are the interoperability gate; a shared runtime package waits until two products need the same executable behavior. Source access and authority filters precede relevance ranking, and historical source refs remain auditable.
