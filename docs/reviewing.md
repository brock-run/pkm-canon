# Reviewer guidance

Common standards: [Canonworks Reviewer Standards — CW-RS-0.2 draft](canonworks/reviewer-standards.md).
The local document is a generated, byte-identical snapshot of the CanonFlow
master, with its immutable source revision and SHA-256 in
[provenance](canonworks/reviewer-standards-source.json). It is readable offline.
This is a proposal for owner review, not ADR acceptance or a claim about
implemented capabilities. Read the actual base/head, local instructions, current
architecture, code and tests. Another repo's rule is not a local requirement.

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

- `node scripts/check-reviewer-standards.mjs`: read the versioned policy; verify the generated snapshot against its provenance.

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

Propose common wording changes in CanonFlow's master through a PR and increment
CW-RS. Consumer updates use the committed source and regeneration procedure in
the common document; never hand-edit a generated snapshot. Review the pin and
content changes together. CI verifies local integrity, not upstream freshness
or adoption. Keep local exceptions here with their reason and decision link.
PR descriptions link relevant work and report actual checks, limitations and
feedback on the latest pushed revision.
