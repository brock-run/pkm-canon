# ADR 0007: Preservation storage descriptors are reusable objects

**Status:** Proposed

## Context

Single-payload records and multi-payload bundles need the same vocabulary for embedded content, package blobs, hashes, media metadata, and payload roles.

## Decision

`SourceNativeReference` is the reusable descriptor for preservation storage. It supports package-relative paths, embedded UTF-8, embedded base64, and policy-controlled external URIs, plus content metadata and hashes.

Exactly the fields required by the selected `storage_kind` must be present; incompatible locator fields are invalid. Package-relative paths may not escape the package root.

## Consequences

- Records and bundles use one storage contract.
- Validators must enforce conditional field rules and path safety.
- External URI presence does not authorize network retrieval.
