# ADR 0014: Database and package migrations are separate

**Status:** Proposed

## Context

Relational deployment state and portable package compatibility evolve for different reasons and at different rates.

## Decision

PostgreSQL schema changes use Alembic and, where relevant, Expand-Migrate-Contract. Canonical package changes use explicit ordered application migrations keyed by `package_schema_version`.

Breaking package changes require a version bump, migration, fixtures, regenerated schemas, and changelog entry.

## Consequences

- Database revision IDs never substitute for package versions.
- Additive changes are preferred on both surfaces.
- Package migrations can run without a database.
