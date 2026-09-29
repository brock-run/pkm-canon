# Roam JSON source profile 0.1.0

This profile maps one Roam graph export to one validated canonical package. The
adapter name and implementation version are recorded independently in the
manifest.

## Identity and replay

- Source scope is the operator-supplied graph name. Source version identity is
  derived from source system, scope, export name, and SHA-256 of the export bytes.
- A page ID derives from `("roam", graph, "uid:" + page_uid)`. A block ID
  follows the same rule with a separate `node` prefix. The shared
  `stable_id` function hashes a JSON array of these components and uses the
  first 24 hexadecimal characters.
- For missing or duplicate UIDs, the adapter uses the source JSON path as its
  deterministic local key and emits a `MISSING_UID` or `DUPLICATE_UID`
  diagnostic. A matching preservation record contains the original object.
- Derived span, relation, attribute, preservation, and diagnostic IDs use
  source-scoped IDs plus deterministic local discriminators. Reprocessing the
  same bytes with the same profile and adapter version yields the same records
  and ordering.
- Missing source timestamps stay null. The wall clock is used only for
  `manifest.created_at` and `source_versions[].observed_at`, explicitly
  run-specific fields. The package ID also includes the access policy so a
  changed policy cannot silently reuse an existing package.

## Mapping and fidelity

| Roam construct | Canonical output |
| --- | --- |
| Page | `Document` |
| Block and nesting/order | `Node` with parent and position |
| Block string | Full-text `Span`; source syntax remains verbatim |
| `Key:: Value` | `Attribute` |
| Page/block reference or embed | `Relation` when the target resolves uniquely |
| Tag | `Relation` with `target_kind=tag` |
| Unknown fields, unsupported macros, or unstructured rich text | Partial diagnostic plus preserved raw JSON object |
| Missing or ambiguous reference target | Unresolved-reference diagnostic plus preserved raw JSON object |

The complete export is captured in the package's source blob, hashed, and
recorded by `SourceVersion`. Each page and block counts as one source object
in the fidelity summary. Multiple diagnostics for one object count as one
partial object. Unsupported constructs are never silently removed from the
source snapshot.

## Limits

The text span retains Roam markup verbatim; it does not yet model every inline
formatting construct. References resolve within one export. Cross-graph links
need a later identity-resolution workflow. A title that maps to multiple pages
is considered ambiguous rather than silently bound to one page.
