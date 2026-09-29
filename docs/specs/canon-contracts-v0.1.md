# Portable canon contracts, v0.1

**Status:** Proposed. This is a cross-product design incubated in Rosetta; only
the generic store port and Rosetta filesystem binding are implemented today.

## Vocabulary

| Term | Shared meaning | Rosetta | Living Knowledge | CanonFlow |
| --- | --- | --- | --- | --- |
| Canon | Governed selection accepted for a bounded purpose, scope, context, and time | Source representation canon | Steward-approved domain knowledge canon | Creator-approved project/branch canon |
| Candidate | Eligible for review, outside canon | Parsed claim or proposed mapping | Extracted claim/concept | Extracted character, rule, or plot change |
| Canonical artifact | Product's accepted immutable version | Validated `CanonicalPackage` | Approved assertion/knowledge-object version or Iceberg snapshot | Approved `ENTITY_VERSION` selected by a checkpoint |
| Projection | Rebuildable serving form | Index/SQL/export | Search/vector/graph/documentation | Chunk/embedding/search index |
| Publication | Audience-facing derivative | Export or methodology manifest | Documentation or agent answer | OutputRun/artifact |

An artifact is canonical **relative to a named canon**, never merely because
its bytes live in a “canonical store.” Canon admission is product policy; store
commit is durable persistence and validation. A source package can be faithful
to a false statement. A domain claim can be approved yet superseded. A story
fact can be true on one branch or at one story time and false on another.

## Minimal portable ports

```python
class CanonStore(Protocol[RefT, CommitT, ArtifactT]):
    def open(self, ref: RefT) -> ArtifactT: ...
    def commit(self, request: CommitT) -> ArtifactT: ...
```

`ArtifactT` is the product result, not a common record wrapper. The adapter
validates its product invariant before exposing a committed artifact. Rosetta
returns `CanonicalPackage`. A CanonFlow checkpoint adapter could return a
`CanonFlowPackage`: an immutable aggregate of project, branch, checkpoint,
selected entity-version refs, context, policy version, and digest, materialized
from its PostgreSQL records without requiring a new package table. An entity
version adapter would have a different `ArtifactT`. A Living adapter could
return an `ApprovedAssertionVersion`, a `KnowledgeObjectVersion`, or a governed
Iceberg snapshot through separate bindings. A store may add its own transaction and
idempotency details. Do not add approval, snapshotting, retrieval, or impact
methods to this port: those are independently replaceable capabilities.

Illustrative bindings (the latter two are design targets, not implementations):

```python
RosettaStore = CanonStore[Path, PackageCommit, CanonicalPackage]
CanonFlowStore = CanonStore[CheckpointRef, CanonFlowCheckpointCommit, CanonFlowPackage]
LivingStore = CanonStore[KnowledgeVersionRef, ApprovedAssertionCommit, ApprovedAssertionVersion]
```

Portable conformance tests should check commit/open round trip, immutable
identity, idempotent retry, collision/conflict behavior, and rejection of an
invalid artifact. Product suites supply their own fixtures and admission
policy. A generic test must never require fields such as `package_id`,
`entity_version_id`, or `assertion_id`.

## Contracts to extract when a second implementation exists

| Capability | Portable fields / behavior | Product-owned policy or payload |
| --- | --- | --- |
| `CanonDescriptor` | `canon_id`, kind, purpose, scope, context dimensions, authority rule version | Which claims are eligible and who may approve |
| `VersionRef` | `canon_id`, artifact kind/id, immutable version id, optional digest | Rosetta package/source ID; Living assertion/table ID; CanonFlow entity version ID |
| `Snapshot` | Immutable ID, descriptor, branch/context, selected version refs, created time, digest, policy version | Selection algorithm and storage layout |
| `PublicationPin` | Publication ID, snapshot ID, actually used version refs, retrieval trace/config ID, generation input hashes, review decision refs | Output shape, publication approval, retention |
| `DependencyEdge` | Versioned `from` and `to` refs, relation kind, evidence, recorded time | Meaning of “supports,” “cites,” “constrains,” or “generated from” |
| `AuthorityContext` | Actor/access, canon, branch, audience, temporal and use context | Authorization rules and domain/creative applicability |
| `ImpactQuery` | Changed version refs, comparison snapshot, edge kinds, traversal direction/depth | Severity, stale policy, regeneration vs review decision |

The corresponding narrow ports can be defined when implemented: an
`AdmissionPolicy` validates a candidate and review decision for a named canon;
a `SnapshotBuilder` returns the product snapshot artifact; a `PinRecorder`
freezes publication inputs; a `DependencyRecorder` writes versioned edges; a
`Retriever` accepts an `AuthorityContext` and returns eligible evidence with
refs; and an `ImpactAnalyzer` returns explained reverse paths. Each has its
own request/result types. Shared tests should assert invariants (immutability,
no candidate self-promotion, hard authority filtering, exact pin closure,
reverse-path explanation) while product tests assert story-time, domain-time,
or source-fidelity rules. This avoids a large shared interface that must know
every product's data model.

`Snapshot` is a closed, validated selection of immutable versions. It is
created atomically; later changes create another snapshot. A stable hash over
the canonicalized selection and policy version detects accidental mutation.
The product may use a Rosetta package ID, an Iceberg snapshot ID, or a CanonFlow
checkpoint ID as its native snapshot identity, provided the portable mapping
is explicit. A snapshot captures *available admitted state* under its canon's
policy: fidelity validation for Rosetta; steward or creator review for the
other two products. A publication
pin captures *actual inputs and decisions used*; it does not make the output
canonical. Pins are immutable after publication. Freshness and access are
re-evaluated for new retrieval requests, even when an old pin remains auditable.
An **execution checkpoint** captures resumable workflow state and is a
different contract from a canon snapshot, even if a workflow checkpoint
references one.

## Retrieval contract

Candidate retrieval is constrained **before ranking** by authorization,
named canon, accepted state, branch, applicable context, and time. Rank the
eligible set, then return evidence with version refs and an exclusion/abstention
reason when appropriate. A dense similarity score never overrides authority.
Rosetta must distinguish faithful source text from an endorsed claim; Living
must apply steward approval and valid/effective time; CanonFlow must apply
branch, story timeline/point of view, creator approval, and spoiler/audience
rules. Search results carry exact refs so a publication can pin what it used.

## Provenance, lineage, and ripple

The [dedicated Rosetta application](provenance-lineage-ripple.md) records how
these semantics apply to source packages and identifies the implementation
checks still needed.

- **Provenance:** origin and responsibility for one version or decision
  (source, actor, activity, timestamp, evidence, transformation).
- **Lineage:** durable directed relationships among versions, runs, datasets,
  snapshots, and outputs. A dependency edge states *why* one object used or
  derived from another. Retain version-level links even if a dataset-level
  lineage system also receives events.
- **Ripple / impact:** reverse traversal of relevant lineage/dependency edges
  from a changed version, followed by comparison against a target snapshot
  and product policy. It yields potentially affected dependents and an
  explanation; it does not automatically declare them wrong or regenerate.

The [W3C PROV-O specification](https://www.w3.org/TR/prov-o/) provides useful
`Entity`, `Activity`, `Agent`, `used`, and `wasDerivedFrom` vocabulary.
[OpenLineage's object model](https://openlineage.io/docs/spec/object-model/)
can publish job/run/dataset lineage,
including dataset versions. Neither replaces the version-level dependency
ledger needed to answer which exact claim, story scene, or output used a changed
version. OpenLineage is an interoperable projection of suitable durable events,
not the only source of impact truth.

Example: a changed source paragraph has provenance back to an export;
Rosetta's parsed node derives from it; a Living claim cites that node; a
CanonFlow output cites an approved entity version. Reverse impact walks the
recorded edges to find dependents. Each product decides whether to review,
re-retrieve, regenerate, or leave the dependent valid in its original context.

## Implementation order

1. Keep the generic store port and Rosetta package adapter small.
2. Give each product a canon descriptor and product-specific admission rule.
3. Introduce immutable snapshot refs and publication pins at the point where
   each product first publishes an output.
4. Record exact version-level dependencies at every transformation/review.
5. Build reverse impact and authority-aware retrieval over those records.
6. Extract shared contract types and conformance fixtures into a separately
   versioned package only after two products implement the same semantics.
