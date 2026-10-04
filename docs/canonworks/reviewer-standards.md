# Canonworks reviewer standards

**CW-RS-0.2 · Draft · 2026-10-04.** Applies to PKM Canon, CanonFlow and Living Knowledge. CanonFlow's `docs/canonworks/reviewer-standards.md` is the authoritative common document. Repo-local `docs/reviewing.md` files record applicability and executable checks. This is a proposal for review, not an ADR acceptance or a claim that every product has implemented every capability.
## RS-01 · Ground findings in the owning repository
Read the PR's base/head, local instructions, current architecture, tests and existing conventions. Cite the changed location, concrete trigger, consequence and applicable rule. Do not import another repository's naming, database, framework or deployment rules. Distinguish a defect from a preference or future enhancement. A review should help decide what must change before merge.
## RS-02 · Preserve product authority and boundaries
Source fidelity, creator approval and domain stewardship are distinct. Extraction or inference creates evidence or candidates, never implicit approval. Review, selection and publication are separate where the product implements them. Shared schemas/fixtures protect portable evidence semantics; extracting a shared runtime requires the existing portfolio gate. Do not add another product's admission policy to make a local slice appear complete.
## RS-03 · Protect exact evidence and history
Verify source identity, version and citations survive the changed path. Historical checkpoints, output pins and decision records remain inspectable. Reject missing, mismatched or stale references rather than silently retargeting them. Preserve ambiguous alternatives and open questions. A digest identifies exact content; a display label, rank or support heuristic is not proof of authority.
## RS-04 · Apply access and security to the actual deployment
For changed protected operations, check authorization on reads and writes and before returning evidence. Test denial paths and input boundaries. Evaluate RLS, credentials, hosting and tenancy against this repository's documented threat model and accepted decisions; do not impose RLS universally or describe service checks as sufficient for every future deployment. Review source rendering and file handling as untrusted input. Private evidence and secrets stay out of commits, logs, fixtures and external review artifacts.
## RS-05 · Test replay, interruption and state transitions where relevant
For changed durable operations, verify idempotent replay, conflicting reuse, restart/interruption recovery, atomic writes and stale/concurrent decisions. A failed operation must leave coherent state and a useful recovery path. Distinguish invalid credentials from denied access to one resource. Changing project/source context must not carry unrelated selections or display stale data under a new label. Apply these checks to the lifecycle changed by the PR, not every unrelated component.
## RS-06 · Review the usable end-to-end path
Run the changed user or operator journey, including a meaningful failure case. Selection, saved state, current scope and next action should be visible. A reset should distinguish clearing a task from removing source data. Preserve keyboard access, focus, readable hierarchy and clear errors. Keep technical identifiers in details when they do not help the immediate task. Synthetic DOM tests protect regressions; visual and browser behavior need browser verification when the changed behavior depends on it.
## RS-07 · Use proportionate, executable verification
Run the repo's supported checks and meaningful regression tests for changed invariants. For service changes, exercise real routes and relevant lifecycle failures; for scripts, execute them; for schemas, check generated artifacts/conformance. Report skips, unavailable dependencies and verification limits. Prefer a test that fails for the observed defect over tests that mirror implementation or blanket coverage/docstring quotas. A small documentation-only PR needs link/content validation, not unrelated service execution.
## RS-08 · Keep contracts and architecture honest
Update affected current/target diagrams and component maps with boundary, schema or data-flow changes. Separate executable behavior from proposed designs and record branch/revision, sources, verification and Linear work. Repo technical docs remain authoritative; Notion mirrors include source revision/digests. ADR status changes require the official decision ledger. Schema/storage naming follows the owning repo; a convention change needs an explicit migration rationale.
## RS-09 · Keep review actionable
Use **Blocking** for a demonstrated correctness, access/privacy, data-loss, authority or contract regression; **Required** for a supported acceptance criterion or repo rule the PR violates; **Suggestion** for an improvement that is safe to defer; **Question** for missing evidence. Explain how to verify a fix. Do not mark a speculative future requirement blocking. Record a reason when declining a bot suggestion, including the repo scope or evidence it misapplied.
## RS-10 · Review the revision that will merge
PRs state the concrete behavior, affected product boundary, linked work and executed checks/limits. After pushing fixes, inspect CI and bot feedback for the latest head; earlier green runs or resolved threads do not prove the new revision. Address valid findings, rerun affected checks and disclose outstanding findings. Bot completion is review evidence, not permission to merge or acceptance of an ADR.
## Applicability by product
- **PKM Canon:** source fidelity, preservation/loss diagnostics, source-scoped immutable identity, validated package commits, access-aware evidence, and explicit approval before activation. Storage and projections follow its local adapters and contract tests.
- **CanonFlow:** creator review, checkpoint selection, separate publication, exact historical pins and product-owned story policy. The isolated story desk is a working-evidence trial, not canon admission. Local service authorization and schema conventions remain scoped to its documented deployment.
- **Living Knowledge:** steward authority, permitted evidence, effective-time/freshness and explicit abstention are proposed design concerns until the bounded pilot implements them. Review design consistency now; do not invent application tests or describe proposed services as running.
## Adoption and changes

Owner: Brock Butler. The version remains Draft until the owner approves adoption
in a reviewed change to this document. Make shared wording changes here through a
CanonFlow PR, increment CW-RS, and record the reason/date and review links. Local
exceptions explain scope and tradeoffs in each repo's guide and link the relevant
accepted decision. Do not silently change instruction files or ADR statuses.

## Distribution and maintenance

CanonFlow owns the editable master for now. PKM Canon and Living Knowledge carry
byte-identical generated snapshots at the same `docs/canonworks/reviewer-standards.md`
path, with source repository, immutable Git revision and SHA-256 in
`docs/canonworks/reviewer-standards-source.json`. Reviewers can read these files
offline. A snapshot is a pinned dependency, not a second place to edit policy.
The source may be on a review branch; its presence does not imply adoption or merge.

Generate a consumer update from a committed CanonFlow checkout:

```sh
node scripts/sync-reviewer-standards.mjs /path/to/pkm-canon /path/to/living-knowledge
```

Review and commit the snapshot/provenance changes in each consuming repo's PR.
Then run `node scripts/check-reviewer-standards.mjs` in that repo. CI checks the
snapshot's recorded digest and provenance without fetching another repository.
This detects local drift; it does not prove the snapshot is the newest upstream
version or that the source is adopted. Re-run sync when adopting a newer revision.

In CanonFlow, run `node scripts/check-reviewer-standards.mjs --canonical`.
Notion is a discoverable mirror with source revision/digest, not the editing home.
If the upstream is unavailable, use the checked-in snapshot and state its version
and pin. If the local document is missing or fails integrity checks, report the
gap and apply available local instructions without inventing unseen requirements.

Hosting decision: one document does not justify a separate repository and
submodule checkout lifecycle. Plain Git snapshots keep ordinary clones and PR
review self-contained. Revisit a dedicated Canonworks repository when several
shared assets need independent ownership, releases and compatibility policies.
Moving the source later changes provenance, not product runtime or authority.

## Draft revision log

- **CW-RS-0.2 · 2026-10-04:** move authority from Notion to CanonFlow and distribute
  pinned, integrity-checked offline snapshots. Shared RS-01 through RS-10 wording
  is unchanged. Notion becomes a mirror. [BRO-66](https://linear.app/brock-better-make/issue/BRO-66)
  tracks owner review. No instruction files or ADR statuses change.
- **CW-RS-0.1 · 2026-10-03:** initial Notion proposal after CanonFlow bot findings
  exposed cross-repository rule leakage and gaps in lifecycle/UI verification.
  Review PRs: [PKM Canon](https://github.com/brock-run/pkm-canon/pull/6),
  [CanonFlow](https://github.com/brock-run/canon-flow/pull/6),
  [Living Knowledge](https://github.com/brock-run/living-knowledge/pull/4).

