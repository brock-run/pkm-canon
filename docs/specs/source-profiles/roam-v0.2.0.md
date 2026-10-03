# Roam JSON source profile 0.2.0

This profile extends [0.1.0](roam-v0.1.0.md). Parser `roam-json:0.3.1`
interprets common export metadata and native references. The profile and parser
version change the package identity; existing review decisions are not carried
onto a new package without a fresh review.

## Field semantics

| Source field | Interpretation | Output and remaining limit |
| --- | --- | --- |
| `uid`, `title`, `string`, `children`, `order` | Page/block identity, title/text, nesting, sibling position | Core `Document`, `Node`, and `Span`; malformed or missing values are diagnosed. |
| `create-time`, `edit-time` | Epoch milliseconds | Core document times or source-specific node times; invalid values are diagnosed. |
| `:create/user`, `:edit/user` | A single `:user/uid` source actor ID | Typed `created_by_uid` / `edited_by_uid` in `pkm/source-roam`. This does not establish an access principal or cross-export person identity. Unexpected shapes are diagnosed. |
| `refs`, `:block/refs` | Two representations of the same ordered target UID list | One `native_ref` relation per unique target, from page or block to a uniquely resolved page/block in the export. Conflicts, malformed arrays, and missing or ambiguous targets are diagnosed; source-native edges remain distinct from links parsed from text. |
| `heading` | Integer level 0–3 | `heading_level` in `pkm/source-roam`; levels 1–3 also set `Node.semantic_kind=heading`. Other values are diagnosed. |
| `text-align` | Known alignment (`left`, `center`, `right`, `justify`) | Validated source presentation in `pkm/source-roam` as `text_align`; not portable layout. Unknown values are diagnosed. |
| `:children/view-type` | Known values (`:bullet`, `:numbered`) | Validated source presentation in `pkm/source-roam` as `children_view_type`; not a portable rendering instruction. Unknown values are diagnosed. |
| `:block/view-type` | Known value (`:outline`) | Validated source presentation in `pkm/source-roam` as `block_view_type`; not a portable rendering instruction. Unknown values are diagnosed. |
| `:log/id`, `props`, `:block/props`, `emojis`, unknown fields | Source-specific data with no defined canonical meaning here | `UNSUPPORTED_FIELD_*` diagnostic and exact linked raw-object preservation. |
| Inline rich text and unsupported macros | Source syntax retained verbatim in the text span | Explicit partial diagnostic and linked raw-object preservation until structured interpretation exists. |

The full source export is stored byte-for-byte in every package. A page or
block with an unnormalized field also receives an exact raw-object
preservation record linked from its diagnostic. An interpreted field is removed
from the unsupported-field warning set only when its value is validated and
mapped with the meaning above. Fidelity counts describe this profile's
coverage, not migration or rendering equivalence.
