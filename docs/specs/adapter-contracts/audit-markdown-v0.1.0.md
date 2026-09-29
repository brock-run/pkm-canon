# Audit Markdown projection 0.1.0

This versioned output adapter renders validated canonical packages for human
inspection. It is a one-way projection, not an Obsidian, Logseq, or Roam
round-trip format.

| Canonical construct | Projection behavior |
| --- | --- |
| Document title and identity | One Markdown file with package, document, and source-version IDs |
| Node hierarchy and order | Indented list in source order |
| Node text | Preserved verbatim inside the list item |
| Exact source location | `evidence-map.jsonl` maps rendered lines to node IDs, source locators, and source hashes |
| Fidelity or unresolved-reference diagnostic | `projection-issues.jsonl` retains the diagnostic code and subject |
| Facets, source-native payloads, full graph, access policy | Remain in the canonical package; not encoded in the Markdown page |

`projection-manifest.json` records the package ID, adapter contract version,
output inventory, hashes, and issue count. A projection can be rebuilt from the
package. Consumers must enforce package access policy before distributing
rendered files.
