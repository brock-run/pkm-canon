# Reviewer guidance

Common standards: [Canonworks Reviewer Standards — CW-RS-0.1 draft](https://app.notion.com/p/3ef899c28af3810dac04e9cac557d530).
The common wording lives in Notion; this file records only this repository's
applicability and verification. CW-RS-0.1 is a proposal for owner review, not an
ADR acceptance or a new claim about implemented capabilities.

Review the actual base/head and this repo's instructions, current architecture,
code and tests. A rule from another repository is not a local requirement.
If Notion is unavailable, disclose that limitation and apply the available local
instructions; do not invent requirements from the inaccessible draft.

## PKM Canon applicability

- RS-02/03: the validated package is the authoritative ingestion result. Preserve
  original bytes, source-scoped identity, evidence resolution and explicit loss
  diagnostics. Projections/indexes are rebuildable; inference is not source truth.
- RS-02/04: methodology/domain proposals require authorized review before
  activation. Check access-aware evidence and denied/restricted paths as changed.
  The loopback ingestion-job API's documented deployment limits are distinct
  from hosted authentication requirements; do not import CanonFlow's DB schema.
- RS-05/07: check deterministic canonical replay, atomic package commits and job
  recovery when affected. Changed profiles/schema namespaces require compatibility
  and identity evidence; existing private packages are not silently rewritten.
- RS-08: read [current](architecture/current-state.md),
  [target](architecture/target-state.md) and [map](architecture/component-map.md)
  for boundary or data-flow changes. Generated schemas follow runtime models.
  Product authority and schema/fixture gates do not imply shared runtime adoption.

## Verification for the changed scope

Use the existing `.venv`, committed lockfile and Make targets. Use synthetic
fixtures; keep private source exports/packages and their excerpts out of PRs.

- `make check`: generated-schema drift, Ruff and the pytest suite.
- `node scripts/check-architecture.mjs`: diagrams, IDs and file links in the three
  files under `docs/architecture/` only; it does not check other docs or anchors.
- Adapter/CLI changes: execute the affected ingest → validate → evidence/review
  path, including a meaningful negative case and replay where relevant.
- Job API/worker changes: exercise the real route and relevant recovery lifecycle.
- Documentation-only changes: check content and resolve relative file links from
  each changed Markdown file, confirming each target exists. Inspect heading
  anchors in the target document and verify external references separately.
  Report this review separately from the architecture checker; unrelated service
  execution is not required by the proposed common standard.

## Maintaining this reference

Propose shared wording changes in Notion with a new CW-RS version; update this
reference through a PR after owner review. Keep local exceptions here with their
reason and decision link. PR descriptions link relevant work and report actual
checks, limitations and feedback on the latest pushed revision.
