# PKM Canon architecture: current state

**Evidence base:** the [PKM Canon tests](../../tests/) and repository checks, verified 2026-10-03. These components are implemented in this repository. The [component map](component-map.md) names code, checks, work items, and decisions.

```mermaid
flowchart LR
  PC00["PC00 Source exports<br>Roam JSON or one Markdown file"] --> PC01["PC01 Source adapters and local job API"]
  PC01 --> PC02["PC02 Versioned canonical package"]
  PC02 --> PC03["PC03 Validation and preservation diagnostics"]
  PC03 --> PC04["PC04 Evidence-linked proposals"]
  PC04 --> PC05["PC05 Review ledger and approved products"]
  PC02 --> PC06["PC06 Rebuildable index and context"]
  PC02 --> PC07["PC07 Shared content snapshot"]
```

The package is the authoritative **source-fidelity** result. A validated package does not approve claims found in its content. The review ledger governs methodology or domain-page proposals separately. Indexes, audit Markdown, and context bundles are derived from the package. `PC07` exports a versioned, source-neutral contract; the synthetic CanonFlow consumer checks its references without importing this runtime.

The local job API binds to loopback, stores resumable job state in SQLite, and delegates package creation to a worker. It is not a hosted authenticated service. Roam support is bounded to the recorded source profile and diagnostics; the current methodology queue is calibrated for the representative graph, not an automatic policy for every future source.
