# PKM Rosetta

Rosetta converts source exports into independently validated, portable
canonical packages. The package is Rosetta's authoritative ingestion result;
search, inference, review outputs, and Markdown pages are derived products.

The current implementation has two source adapters: Roam JSON and one
repository Markdown file. Both produce source-version capture, structured
content, preservation artifacts, fidelity diagnostics, and a manifest with
file hashes and counts. The Roam product proposes methodology rules from
attributes. The Markdown product proposes explicit ownership claims. Neither
proposal becomes active without a review event.

## Quick start

Use the repository's Python environment and committed lockfile:

```sh
uv sync --extra dev --locked
source .venv/bin/activate
make check
pkmcanon ingest-roam graph.json my-graph output/roam-package
pkmcanon validate output/roam-package
pkmcanon audit-fidelity output/roam-package --top 20
pkmcanon ingest-markdown docs/context-api.md platform output/markdown-package --source-path docs/context-api.md
```

The `pkmcanon` command is installed into `.venv/bin`. Use that explicit path
when the virtual environment is not activated.
For a private source, pass the intended reviewer identity with
`ingest-roam --principal REVIEWER_ID` (or `ingest-markdown --principal`), then
use the same ID with `propose-methodology --principal` and in the review policy.
The default `local-operator` identity is for local demonstrations.

## Reviewable product flow

```sh
pkmcanon propose-methodology output/roam-package output/methodology-proposals.jsonl
pkmcanon render-methodology-review output/roam-package output/methodology-proposals.jsonl output/methodology-review.html
pkmcanon propose-domain-claims output/markdown-package output/domain-proposals.jsonl
```

Each proposal file contains stable IDs, a typed payload, exact evidence
references, and a source-package ID. The review HTML ranks draft rules by
evidence count and shows a few escaped citation previews. The command does not
upload it or record decisions. The file contains source excerpts; keep the
output private and inspect full evidence before review. Methodology statements
identify their Roam graph scope.
Record an approval or rejection with:

```sh
pkmcanon review PACKAGE PROPOSALS PROPOSAL_ID POLICY_JSON REVIEW_LEDGER REVIEWER_ID approved
pkmcanon render-methodology-review PACKAGE PROPOSALS output/methodology-review.html --ledger REVIEW_LEDGER --policy POLICY_JSON
```

`examples/local-review-policy.json` is a local demonstration policy.
Production deployments must supply their own authorized reviewer policy.
Publication reads the append-only review ledger and selects approved
proposals only:

```sh
pkmcanon publish-methodology PACKAGE PROPOSALS REVIEW_LEDGER POLICY_JSON output/active-methodology.json
pkmcanon publish-domain-page PACKAGE PROPOSALS REVIEW_LEDGER POLICY_JSON output/reviewed-domain.md
```

`pkmcanon context PACKAGE "owner" ownership` assembles an access-aware
lexical evidence bundle from the package. The lexical implementation is a
small local projection. `pkmcanon build-index PACKAGE output/index.json`
creates a rebuildable lexical and native-link index; pass
`--index output/index.json` to `pkmcanon context` to use it. Hybrid retrieval
and cross-source resolution remain future work.

`pkmcanon project-shared PACKAGE output/content-snapshot.json` exports the
source-neutral content contract. `pkmcanon project-markdown PACKAGE
output/audit-pages` creates an audit-oriented Markdown projection and
evidence sidecars; it is not a round-trip migration adapter.

## Local ingestion jobs

The local API accepts a bounded source upload and returns `202` with a stable
job ID. A separate worker validates and commits its package; job state is
stored in SQLite so the worker can resume after interruption. Start the API
on loopback and process queued jobs with:

```sh
pkmcanon serve-jobs output/jobs --port 8775
pkmcanon work-jobs output/jobs
```

Upload with `POST /api/v1/ingest/roam?source_scope=graph&native_id=export.json`
or `/api/v1/ingest/markdown?source_scope=repo&native_id=docs/page.md`, sending
the source file as the raw request body. Poll `GET /api/v1/ingest/jobs/{job_id}`; a completed job
names its validated package. The API has no authentication and is intended for
local development on `127.0.0.1`. An external deployment needs an authenticated
transport and worker supervision.

Labeled retrieval cases use the `evaluation-case` schema and name expected
canonical node IDs. Run `pkmcanon evaluate PACKAGE INDEX CASES RESULTS
PROPOSALS` to measure recall and abstention. Missed, accessible gold evidence
becomes a typed retrieval-change proposal for review; the evaluator never
silently changes the index or source model.

## Contracts and scope

- Runtime records live in `src/pkmcanon/models.py`. Committed JSON Schemas
  are generated under `docs/specs/schemas/`; `make check` fails on drift.
- Source identity and known losses are specified in
  `docs/specs/source-profiles/`. Each package retains the original source
  bytes and records its hash.
- The validated package is committed atomically through the product-neutral
  `CanonStore[Ref, Commit, Artifact]` port. Rosetta binds it as
  `CanonicalStore = CanonStore[Path, PackageCommit, CanonicalPackage]` and
  provides a filesystem implementation. No database or hosted service is
  needed to validate a package.
- The V1 design and implementation plan under `docs/specs/` describe later
  API, PostgreSQL, retrieval, inference, and export work. Those sections are
  proposals, not claims that the features are already implemented.
