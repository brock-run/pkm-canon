# ADR 0020: Name the canon and keep portable contracts product-neutral

**Status:** Proposed

## Context

PKM Canon's “canonical package” is authoritative for faithful source capture. A
governed domain claim or a creator-approved fictional state makes a different
authority claim. Calling all three objects “canonical” without naming the
canon invites accidental promotion of imported text into accepted knowledge.

PKM Canon's original `CanonicalStore` returned `CanonicalPackage` from two paths,
which made the storage port unsuitable for the other products.

## Decision

- A **canon** is a governed, versioned selection of representations or
  assertions accepted as authoritative for a named purpose, scope, context,
  and time under explicit admission and revision rules. It is a bounded
  authority claim, never a claim of universal truth.
- **Canonical** means selected by or conforming to a *named* canon. APIs and
  prose should name the canon or its kind when the meaning is ambiguous.
- PKM Canon's **source canon** governs whether a package faithfully captures a
  source version. It does not endorse statements in that source. A parsed
  assertion remains a candidate until a separate domain or creative review.
- The portable storage port is `CanonStore[Ref, Commit, Artifact]`. Each product
  owns those three types and its validation/admission rules. PKM Canon binds the
  port to `Path`, `PackageCommit`, and `CanonicalPackage` in `storage.py`.
- Snapshot, publication pin, dependency, lineage, impact, and retrieval
  contracts are specified in [the portable contract design](../specs/canon-contracts-v0.1.md).
  They are separate capabilities, rather than mandatory methods on the store.
- Provenance, lineage, and ripple have separate meanings and PKM Canon-specific
  checks in [their dedicated design](../specs/provenance-lineage-ripple.md).
- A generated output, projection, index, or AI proposal does not enter any
  canon by being stored or cited. Its admission requires the canon's policy.

## Consequences

Existing package callers use a `PackageCommit` request. PKM Canon keeps its
validated filesystem package and atomic commit behavior. A future shared
library may extract the generic port and portable value contracts, while
product adapters and policies remain in their own repositories.
