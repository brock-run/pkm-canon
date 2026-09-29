# PKM Rosetta Migrator

PKM Rosetta Migrator is a foundation for translating personal knowledge-management systems without flattening away what makes them useful. It begins with Roam Research exports and is designed to grow into a versioned interchange layer for systems such as Obsidian, Logseq, Notion, Apple Notes, and Google Docs.

The name reflects the central idea: a personal knowledge base is more than a collection of files. It contains nested thought, links, references, metadata, habits of organizing, and traces of how someone learns and works. This project preserves that structure, makes its conversion auditable, and can later help surface the philosophies, principles, and working methods embedded in it.

## What V1 does

V1 is a deliberately narrow, governed workflow:

1. Accept a Roam JSON export.
2. Produce a validated canonical package on disk.
3. Preserve source-native constructs that cannot yet be normalized faithfully.
4. Load the validated package into an operational database for retrieval and analysis.
5. Propose an evidence-grounded methodology manifest for human review.
6. Publish only explicitly approved rules, plus an audit-oriented Markdown projection.

It is not a real-time sync service, a general-purpose chat interface, a cross-vault deduplication engine, or an automatic writer to an external PKM.

## Design principles

- **Preserve before projecting.** Raw exports and unsupported constructs remain recoverable; no source object is silently discarded.
- **One portable source of truth.** The canonical package—manifest, JSONL records, diagnostics, and preserved blobs—is authoritative. Databases, embeddings, AI outputs, and exports are derived from it.
- **Translate semantics, not just text.** Documents, nested nodes, rich-text spans, relations, and attributes provide a durable model for knowledge graphs rather than a Roam-shaped data dump.
- **Use a flexible foundation without a vague core.** Core records are strict; deliberate extensions use typed, namespaced facets; opaque payloads use preservation artifacts.
- **Keep humans in the loop.** A model may propose a methodology rule, but every active rule must be evidence-linked and explicitly approved.
- **Build the first vertical slice simply.** Roam JSON is the only V1 source. Future inputs and outputs are anticipated in the architecture, not prematurely implemented.

## Current state

This repository is an early scaffold, not yet an end-to-end V1 service.

Already present:

- Pydantic models for core and preservation artifacts.
- Draft JSON Schema contracts and schema-validation utilities.
- A minimal canonical-package example.
- An initial Roam parser and Typer CLI stub.
- A V1 PRD, technical specification, implementation plan, and architecture decision record set.

Still required before V1:

- reconcile runtime models with committed schemas and automate schema-drift checks;
- define a complete manifest, detailed diagnostics, and package-level validation;
- make IDs, ordering, and parser output deterministic;
- finish a complete Roam-to-package writer, API job lifecycle, and safe package publication;
- build the PostgreSQL projection, retrieval, inference/review workflow, and audit Markdown projection;
- establish deployment, access control, retention, recovery, and end-to-end release evidence.

The detailed plan, including work-item acceptance criteria and release decisions, is in [the implementation plan](docs/specs/implementation-pkm-migrator-v1.md).

## Canonical package in brief

Each completed ingestion produces a portable package similar to:

```text
<package-root>/
  manifest.json
  documents.jsonl
  nodes.jsonl
  spans.jsonl
  relations.jsonl
  attributes.jsonl
  preservation_records.jsonl
  preservation_bundles.jsonl
  diagnostics.jsonl
  blobs/
```

The manifest identifies the package and source export, records contract versions and an inventory, and summarizes fidelity. JSONL makes record families streamable, diffable, and independently inspectable. Preservation records and bundles retain source-native payloads—such as unsupported macros, query definitions, rendered previews, or attachments—without contaminating the normalized core.

## Repository guide

| Path | Purpose |
| --- | --- |
| [`docs/specs/`](docs/specs/) | Product requirements, technical design, implementation plan, and JSON Schema contracts. |
| [`docs/adr/`](docs/adr/) | The architecture decisions that govern package ownership, scope, validation, identity, preservation, migration, provider configuration, and human approval. |
| [`docs/brainstorm/`](docs/brainstorm/) | Product and architecture exploration that explains the project's broader intent. |
| [`examples/minimal-package/`](examples/minimal-package/) | Small canonical-package fixture for development and validation. |
| [`src/pkmcanon/`](src/pkmcanon/) | Current package models, loader, validator, CLI, and Roam parser scaffolding. |
| [`tests/`](tests/) | Initial validation and package-shape tests. |
| [`input/`](input/) | Local source-material workspace. Raw exports are intentionally ignored by Git. |

## Key documents

- [Product requirements](docs/specs/prd-pkm-migrator-v1.md)
- [Technical design](docs/specs/design-pkm-migrator-v1.md)
- [Implementation plan and acceptance criteria](docs/specs/implementation-pkm-migrator-v1.md)
- [ADR index](docs/adr/README.md)

## Development notes

The project declares Python 3.11+ as its runtime baseline. The current scaffold has not yet completed its reproducible test/bootstrap workflow; that is now part of the V1 release work. Treat the implementation plan as the source for current engineering status rather than assuming every stub is production-ready.

Raw Roam exports can contain highly personal material. Keep them in `input/raw/` or another protected location: this path is intentionally ignored by Git. Commit sanitized fixtures only.

## Vision beyond V1

The long-term opportunity is a durable personal-knowledge substrate: one that can preserve meaning across changing tools, make conversion trade-offs visible, support multiple representations of the same knowledge, and help a person examine the operating system expressed in their notes.

V1 earns that future by proving a smaller claim first: a Roam export can become a deterministic, validated, loss-minimizing package whose downstream interpretations remain traceable to the source.
