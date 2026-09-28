# ADR 0004: Canonical packages use JSONL record files

**Status:** Proposed

## Context

Canonical packages must support large graphs, streaming, reviewable diffs, and partial processing without depending on a database engine.

## Decision

Each package has one JSON manifest and one homogeneous JSONL file per record family. Detailed diagnostics also use JSONL. Source-native payloads use package-relative blob references when embedding is unsuitable.

The manifest inventories every present or intentionally empty record family with counts and hashes.

## Consequences

- Records can be streamed and validated line by line.
- File ordering and newline rules must be deterministic.
- Cross-record integrity requires package-level validation beyond per-line schemas.
- SQLite or DuckDB mirrors may be derived but are not canonical packaging formats.
