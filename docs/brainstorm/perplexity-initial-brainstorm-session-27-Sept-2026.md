<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# What are the differences between and options for using Roam Research exports in EDN, JSON, and msgpack formats?

Roam’s EDN, JSON, and MessagePack exports are alternative serializations of the same graph-oriented data, but they target different workflows: **EDN for Roam-native fidelity and Clojure tooling, JSON for interoperability and inspection, and MessagePack for compact machine-to-machine storage or transfer.** Roam’s export menu exposes all three formats.[^1_1]

## At a glance

| Format | What it is | Best for | Strengths | Trade-offs |
| :-- | :-- | :-- | :-- | :-- |
| **EDN** | Clojure’s extensible data notation | High-fidelity backup/restore, Clojure/BB tooling | Native fit for Roam’s Clojure lineage; expressive types and keywords; text-readable | Less universally supported than JSON |
| **JSON** | Ubiquitous text interchange format | ETL, scripts, migration, Git-friendly snapshots, analytics | Easy to inspect, diff, parse, and load across Python, JS, SQL, jq, etc. | Larger files; may not represent every native type or restore-oriented detail as naturally |
| **MessagePack** | Compact binary JSON-like encoding | Efficient archival, transport, APIs, large-graph pipelines | Smaller and often faster to serialize/parse than text JSON | Not human-readable; requires a decoder/library |

## EDN

Use **EDN** when you want the closest practical fit to Roam’s internal data model or are working in Clojure/ClojureScript. EDN is plain text, but it supports richer notation than JSON, including keywords, sets, tagged values, and other Clojure-oriented structures.

For a **disaster-recovery backup**, EDN is usually the conservative choice: retain periodic immutable exports and validate restoration only in a disposable test graph, not your production graph. Community guidance notes that full EDN restore can overwrite an existing graph, whereas content-oriented JSON/Markdown workflows are more convenient for selective extraction or migration.[^1_2]

## JSON

Use **JSON** as the default for most engineering and knowledge-extraction workflows. It is the easiest format to process with Python, JavaScript/TypeScript, data pipelines, vectorization jobs, graph transformations, or static-site and Markdown conversion tooling.

A typical Roam JSON export is a list of page objects; pages contain titles and hierarchical `children`, while blocks commonly contain a `uid`, `string`, timestamps, editor metadata, and nested children. That makes it straightforward to recursively flatten blocks, preserve page/block context, parse `[[page links]]` and block references, and emit normalized tables such as `pages`, `blocks`, `links`, and `block_attributes`.[^1_3]

```python
import json

with open("roam-export.json") as f:
    pages = json.load(f)

def walk(blocks, page_title, parent_uid=None):
    for position, block in enumerate(blocks or []):
        yield {
            "page_title": page_title,
            "uid": block.get("uid"),
            "parent_uid": parent_uid,
            "position": position,
            "text": block.get("string", ""),
        }
        yield from walk(block.get("children"), page_title, block.get("uid"))

rows = [
    row
    for page in pages
    for row in walk(page.get("children"), page["title"])
]
```

Be aware that third-party documentation has observed that some presentation and revision-history details may not appear in JSON exports, such as “view as document” versus numbered-list display settings and block versions.[^1_3]

## MessagePack

Use **MessagePack** when your concern is **storage footprint, transfer speed, or repeated programmatic ingestion** rather than manual review. It is a binary encoding designed to represent structured data compactly, so it is useful for scheduled backups to object storage, synchronization between services, or ingestion of large graphs where JSON’s whitespace and textual overhead are undesirable.

It is a poor primary format for a personal “open the file and inspect it” backup. Keep a JSON or EDN companion export if you need easy audits, version-control diffs, or recovery without specialized tooling.

Example decoding in Python:

```python
import msgpack

with open("roam-export.msgpack", "rb") as f:
    export = msgpack.unpackb(f.read(), raw=False)
```


## Practical choices

- **Personal backup strategy:** Keep both **EDN** and **JSON**, dated and immutable. Use EDN as your restore-oriented artifact and JSON as the portable, inspectable artifact.[^1_2][^1_3]
- **AI/RAG or analytics pipeline:** Start with **JSON**. Normalize pages and blocks, retain UIDs and parent/ordering relationships, and generate derived Markdown or chunks separately.
- **Clojure graph tooling:** Prefer **EDN**; it avoids needless translation into a less expressive interchange format.
- **High-volume automated sync:** Prefer **MessagePack** if your consumer supports it, but retain JSON for debugging and auditability.
- **Migration to Markdown-based tools:** Start from **JSON** unless the target tool explicitly documents EDN support; existing conversion guidance commonly directs users to Roam’s JSON export.[^1_4]


## Recommended export pattern

For a robust, tool-friendly archive, produce all three only if you have an actual consumer for MessagePack:

1. **Weekly EDN** — recovery / native preservation.
2. **Daily JSON** — analytics, scripts, diffs, AI ingestion, and migration.
3. **Optional MessagePack** — compact operational snapshots where space or throughput matters.
4. Store a manifest beside every export with graph name, export timestamp, Roam format, SHA-256 checksum, and counts of pages/blocks.

The key architectural point is that export format is not your information architecture: preserve raw exports unchanged, then build a versioned normalization layer from JSON or EDN for your downstream search, graph, analytics, or agent workflows.

<span style="display:none">[^1_10][^1_11][^1_12][^1_13][^1_14][^1_15][^1_5][^1_6][^1_7][^1_8][^1_9]</span>

<div align="center">⁂</div>

[^1_1]: https://roamdocs.fyi/help/export

[^1_2]: https://www.reddit.com/r/RoamResearch/comments/mbcnfl/have_you_guys_used_the_new_back_up_option/

[^1_3]: https://www.scribd.com/document/786555307/Lecture-Course-Pentest-english

[^1_4]: https://marph91.github.io/jimmy/formats/roam_research/

[^1_5]: https://discuss.logseq.com/t/export-to-roam-json-and-edn-does-not-work/5080

[^1_6]: https://www.academia.edu/129878862/A_Blueprint_for_the_Living_Future

[^1_7]: https://news.ycombinator.com/item?id=26326662

[^1_8]: https://beepb00p.xyz/myinfra-roam.html

[^1_9]: https://github.com/avelino/roamresearch-export-block

[^1_10]: https://davidbieber.com/snippets/2020-04-25-roam-json-export/

[^1_11]: https://lists.opensuse.org/archives/list/arm@lists.opensuse.org/2021/2/

[^1_12]: https://leastfixedpoint.com/tonyg/tweet/

[^1_13]: https://cran.imr.no/web/packages/available_packages_by_date.html

[^1_14]: https://www.debian.org/devel/wnpp/work_needing.zh-tw.html

[^1_15]: https://info.comodo.priv.at/blog/tags/computer/


---

# I'd like to convert a few graphs for use in Obsidian and Logseq DB. I'd like to maintain as much information and fidelity as possible, so I'd like to find methods that make these conversions as complete as possible. Please research options.

For **maximum fidelity**, treat Roam conversion as a preservation-and-projection problem rather than a one-click import. Keep each original Roam export untouched, build a canonical normalized graph from the export, then generate separate Obsidian and Logseq DB targets from it; that avoids letting either target’s importer become your only record of IDs, hierarchy, links, and metadata.[^2_1]

## Recommended approach

Create these artifacts per Roam graph:

1. **Raw preservation set:** Export and retain EDN, JSON, Markdown, and assets, with a timestamp and checksum.
2. **Canonical graph package:** Parse Roam JSON into durable tables or JSONL—`pages`, `blocks`, `edges`, `attributes`, `assets`, and `queries`—while retaining original Roam UIDs and source-graph identity.
3. **Two projections:** Generate an Obsidian vault and a Logseq-importable Markdown graph independently from the canonical package.
4. **Reconciliation report:** Measure pages, blocks, parent-child edges, page references, block references, attributes, tasks, dates, queries, and asset-link resolution before and after import.

Roam JSON is usually the best working source because it represents pages and recursively nested blocks with block IDs and text content, making it much more suitable for structured migration than Markdown alone.[^2_2]

## Use each export deliberately

| Roam export | Role in migration | Why retain it |
| :-- | :-- | :-- |
| **EDN** | Recovery-grade source / fidelity reference | Most aligned with Roam’s native data model and useful if you later need a more complete reconstruction |
| **JSON** | Primary transformation input | Supports deterministic parsing of hierarchy, page/block IDs, attributes, references, and timestamps [^2_2] |
| **Markdown** | Human-readable fallback and attachment/link review | Lets you inspect rendered content and compare destination notes manually |
| **MessagePack** | Optional compact archival copy | Useful for storage efficiency, but not ideal as the main conversion source because it is binary |

Do not discard block UIDs even if the destination cannot use them natively. Persist them in frontmatter, HTML comments, or a sidecar mapping file because they are the stable crosswalk for fixing broken references, deduplicating cross-graph imports, and tracing provenance.

## Obsidian path

Obsidian is file-first, so optimize for readable Markdown while adding durable provenance metadata. Use the official importer as a baseline for a pilot, but keep your own JSON-derived representation as the authoritative migration artifact; a one-click import is valuable for speed, not for proving fidelity.[^2_3]

### Vault structure

A practical multi-graph layout:

```text
Roam-Migration/
  _migration/
    manifest.json
    uid-map.jsonl
    links.csv
    unresolved-links.csv
    assets-map.csv
  Graph-A/
    Pages/
    Journals/
    _Roam-Queries/
    _Roam-Embedded-Blocks/
  Graph-B/
    Pages/
    Journals/
    _Roam-Queries/
    _Roam-Embedded-Blocks/
  _assets/
```

Use graph-prefixed paths or frontmatter IDs to prevent same-title pages in separate Roam graphs from silently merging. Since you expect overlap across graphs, avoid using title equality as identity; use an immutable key such as `roam://<source-graph>/<uid>` and make any deduplication decision explicit.[^2_3]

### Frontmatter contract

Put migration metadata in every generated note:

```yaml
---
source_system: roam
source_graph: Graph-A
roam_page_uid: abc123
roam_exported_at: 2026-09-27
created_at: 2022-03-10T14:22:00Z
edited_at: 2025-11-19T08:04:00Z
aliases:
  - Original alternate title
migration_status: imported
---
```

For blocks, preserve the original UID in a trailing non-rendering marker:

```markdown
- Project decision rationale <!-- roam:block-uid=xyz789 -->
```

This enables a later tool to resolve `((xyz789))` references even if an Obsidian note gets renamed or moved.

### Fidelity decisions

| Roam feature | Obsidian representation | Fidelity |
| :-- | :-- | :-- |
| Page reference `[[Page]]` | Obsidian wikilink `[[Page]]` | High |
| Nested blocks | Markdown lists with indentation | High for hierarchy; block identity needs a retained UID |
| Block reference `((uid))` | Link to an anchor, generated block note, or transclusion-compatible target | Medium to high with a UID map |
| Block embed | Generated transclusion / embed note or quoted snapshot with source UID | Medium; semantics differ |
| Attributes / `key:: value` | YAML frontmatter for page-level values; inline fields or Dataview fields for block-level values | Medium to high |
| Daily Notes | Dated notes in a dedicated folder, ISO filename | High |
| TODO / DONE | Tasks plugin-compatible Markdown tasks | High for status; preserve original timestamps separately |
| Queries | Preserve original query as fenced source plus manually rebuild with Dataview/Bases | Low for executable equivalence |
| Aliases | YAML `aliases` | High |
| Attachments | Centralized asset directory plus rewritten relative links | High if every asset is copied and mapped |

Avoid converting every Roam block into its own Obsidian note. That preserves addressability but creates thousands of files and substantially weakens usability. Prefer page-level Markdown notes, preserve block UIDs inline, and create standalone block-addressable notes only for blocks that are referenced or embedded elsewhere.

## Logseq DB path

For a Roam-style block graph, Logseq is the closer conceptual target. Its historical Roam JSON import recognizes block references and embeds and maps date pages for Logseq usage, although query cleanup and attachment handling still require review.[^2_4]

Logseq DB, however, is not merely “Logseq with a new storage engine.” It has typed node properties, tag entities, block/page behavior convergence, and a distinct treatment of tags and references.[^2_5]

### Safest route

Use a staged migration:

1. **Roam JSON to classic Logseq file graph** using Logseq’s Roam JSON importer as a benchmark.
2. **Validate the file graph** against the canonical JSON package: hierarchy, references, tasks, dates, properties, and assets.
3. **Convert file graph to DB graph** with Logseq DB’s file-to-DB importer.
4. **Choose explicit tag conversion semantics** during the DB import.
5. **Enable Markdown Mirror** after validation if you want an external Markdown projection for search, Git-style review, or interoperability.

Logseq DB documents a file-graph-to-DB import path, and its graph export/import system includes a database-oriented SQLite option as well as EDN-oriented data export. Recent Logseq DB releases also provide a Markdown Mirror that writes a synchronized Markdown projection and embeds stable block IDs in comments, which is useful for external tooling and migration auditability.[^2_6][^2_7]

### Tag and property choices

Do not blindly map every Roam `#tag` or `[[page reference]]` into a Logseq DB tag. In Logseq DB, tags, page references, and typed properties are distinct concepts; its importer can convert all tags to DB tags, convert only selected tags, or leave some as pages/references.[^2_8][^2_9]

A durable policy is:


| Roam construct | Logseq DB target |
| :-- | :-- |
| Entity class, such as Person, Project, Meeting, Book | DB tag, with a defined schema |
| Relationship, such as author, owner, related-to | Node-type property |
| Free-form topical link | Page reference |
| Narrow facet / label | Tag, only if it needs inherited schema or table behavior |
| Key-value attribute | Typed property where the type is reliable; otherwise text |
| Query | Preserve original source, then rebuild as DB query or view |
| Daily Notes page | Journal |
| Page/block embed | Node embed, followed by manual validation |

Logseq DB supports typed values including text, number, date, checkbox, URL, and node references; node properties are especially relevant for converting explicit Roam relationships into queryable graph edges.[^2_5]

## Cross-graph deduplication

Do **not** deduplicate during initial conversion. First import every graph with source provenance intact, then classify candidates:

- **Exact duplicates:** normalized block content, same source identifiers, or byte-identical content.
- **Likely duplicate pages:** same normalized title plus high content similarity.
- **Semantic duplicates:** different titles but substantially overlapping content or common external identifiers.
- **Intentional shared concepts:** same name but graph-specific context; keep separate and link them instead.

For each merge, keep a merger ledger:

```yaml
canonical_id: entity:project:acme-platform
sources:
  - graph: Work
    roam_page_uid: 7kP2d
  - graph: Personal
    roam_page_uid: 3mZ8q
decision: merged
confidence: 0.96
reviewed_at: 2026-09-27
```

This aligns with your durable-Obsidian plus graph-workbench model: canonical IDs, provenance, and a one-way promotion workflow prevent the destinations from becoming inconsistent shadow systems.[^2_1][^2_10]

## Validation harness

Build a migration test corpus before converting entire graphs:

- 10 ordinary pages with deep block nesting.
- 5 daily-note pages.
- 5 blocks referenced from multiple pages.
- 5 block embeds.
- 5 pages with attributes, tasks, or query blocks.
- 5 notes containing images, PDFs, external links, and attachments.
- A sample of duplicate page titles across graphs.

Then run structural checks:

```text
Pages:             source vs target
Blocks:            source vs target
Parent-child edges: source vs target
Page links:        source vs resolved / unresolved target
Block refs:        source vs resolved target
Embedded blocks:   source vs repaired / intentionally flattened
Attributes:        source vs typed / text / unmapped target
Assets:            source vs copied / broken links
Tasks:             source vs target states and dates
Queries:           source vs preserved / rewritten / retired
```

Treat non-equivalence as an explicit outcome, not an accidental loss: classify every discrepancy as **preserved**, **translated**, **flattened intentionally**, **repairable**, or **not representable**.

## Best option for you

Given your intended architecture, I would use:

- **Obsidian as the long-lived, Git-manageable narrative corpus**—Markdown generated from Roam JSON, with source UIDs, graph provenance, asset manifests, and a reproducible importer.
- **Logseq DB as the exploratory block and typed-property workbench**—import first through a validated Logseq file graph, then convert to DB and selectively promote high-value entity types into tags and node properties.
- **A canonical migration package as the source of truth**—not either target application’s internal representation.

That gives you portability, recoverability, deterministic re-runs, and a clean path to later build a separate property-graph or agent-retrieval layer without coupling it to an individual PKM application.[^2_1]

<span style="display:none">[^2_11][^2_12][^2_13][^2_14][^2_15][^2_16][^2_17][^2_18][^2_19][^2_20]</span>

<div align="center">⁂</div>

[^2_1]: https://www.perplexity.ai/search/459b668f-8e88-4d1a-be5b-49b6ebaf3ebc

[^2_2]: https://www.scribd.com/document/786555307/Lecture-Course-Pentest-english

[^2_3]: https://www.perplexity.ai/search/686396b2-79a4-4ff6-98e3-b7d6e131a6bb

[^2_4]: https://discuss.logseq.com/t/can-i-effectively-import-block-references-from-roam-research-so-they-link-across-pages/4290

[^2_5]: https://www.academia.edu/129878862/A_Blueprint_for_the_Living_Future

[^2_6]: https://discuss.logseq.com/t/whats-new-with-logseq-db-may-16th-2026/35020

[^2_7]: https://github.com/logseq/docs/blob/master/db-version.md

[^2_8]: https://discuss.logseq.com/t/data-structures-for-bridging-logseq-md-to-logseq-db/34851

[^2_9]: https://logseq.io/page/e87c7359-51f7-44fe-87b3-4a0cd9f2dee3/695feeec-88be-4c5b-8bf2-572513c2f730

[^2_10]: https://www.perplexity.ai/search/1d7272ef-64ee-42e2-8261-5da79438ebab

[^2_11]: https://github.com/logseq/logseq/issues/4125

[^2_12]: https://github.com/logseq/logseq?ref=selfh.st

[^2_13]: https://discuss.logseq.com/t/converting-importing-existing-text-and-markdown-notes-into-logseq/27318

[^2_14]: https://www.atlasworkspace.ai/blog/roam-research-alternative

[^2_15]: https://nesslabs.com/roam-to-logseq

[^2_16]: https://fabric.so/comparison/logseq-vs-roam-research

[^2_17]: https://github.com/logseq/logseq/discussions/7863

[^2_18]: https://www.reddit.com/r/OrgRoam/comments/1fg43pw/conversion_script_logseq_to_org_roam/

[^2_19]: https://bellingcat.gitbook.io/toolkit/more/all-tools/logseq

[^2_20]: https://dexi.net/compare/roam-research-vs-logseq


---

# I agree that I should convert first to a canonical migration package as the source of truth and then build conversinos to Obsidian, Logseq, Logseq DB, and anything else I want to use in the future. Are there any existing examples I can use to start from, or should I build this from scratch?

You should **not** start entirely from scratch. There are useful building blocks already available, but I would not adopt any existing converter as the canonical source of truth because the available tools are mostly destination-specific and optimized for “good enough import,” not for a reusable, fidelity-first migration layer.[^3_1][^3_2]

## Best starting points

The strongest existing foundation on the Obsidian side is Obsidian’s official Importer plugin, which supports both **Roam Research** and **Logseq** imports and includes a real test-fixture-based conversion framework. That makes it valuable as a reference implementation for Markdown projection rules, expected outputs, edge cases, and regression testing, even if you do not use it as your canonical engine.[^3_1]

A second useful reference is **rj2obs**, a focused Roam JSON to Obsidian converter that explicitly preserves referenced block IDs, rewrites block references and embeds into Obsidian-compatible links, converts daily notes to ISO dates, and adds YAML headers with creation dates. It is smaller and easier to understand than Obsidian Importer, so it is a good place to study concrete block-reference handling.[^3_3]

## What exists today

| Project | Good for | Why it helps | Why it is not enough alone |
| :-- | :-- | :-- | :-- |
| [Obsidian Importer](https://github.com/obsidianmd/obsidian-importer) | Reference architecture, test corpus ideas, Obsidian projection behavior | Supports Roam and Logseq imports, converts to Markdown, and has structured fixtures and expected-output tests. [^3_4] | It is target-specific, Markdown-oriented, and not intended to be a canonical graph package. [^3_4] |
| [rj2obs](https://github.com/renerocksai/rj2obs) | Studying Roam block-ref preservation | Preserves referenced Roam block IDs and rewrites block refs/embeds into Obsidian-friendly links. [^3_3] | Narrow scope, older, and built specifically for Obsidian output rather than reusable normalized graph modeling. [^3_3] |
| [Jimmy](https://marph91.github.io/jimmy/formats/roam_research/) | Generic note-format conversion ideas | Documents a Roam-to-Markdown conversion path from exported data. [^3_5] | Broad converter, but not a fidelity-first canonical graph model. [^3_5] |
| Logseq Roam JSON import behavior | Benchmark for Logseq compatibility | Community documentation indicates Logseq can import Roam JSON and recognizes block references/embeds. [^3_6][^3_7] | Import fidelity has had edge-case limitations, including date preservation and block-reference behavior across versions. [^3_8] |

## Recommendation

I would build a **small custom canonical core** and borrow projection logic and test ideas from existing tools. The right pattern is: parse Roam JSON once into your own normalized model, preserve every recoverable source identifier and edge, then generate Obsidian, Logseq, and Logseq DB outputs with adapters.[^3_9][^3_10]

That means your “from scratch” work should be limited to the parts that existing tools do not solve well:

- Canonical schema design: pages, blocks, parent-child order, page refs, block refs, embeds, attributes, tasks, timestamps, assets, and source provenance.
- Stable identity model: `source_graph`, `source_uid`, `canonical_id`, and alias/merge tracking across graphs.
- Loss accounting: every projection marks fields as preserved, translated, flattened, deferred, or unsupported.
- Re-runnable adapters: Obsidian Markdown, classic Logseq Markdown, Logseq DB staging format, and future graph/database exports.


## Best implementation path

A pragmatic plan would be:

1. **Use Obsidian Importer and rj2obs as reference corpora**, not as the core engine.[^3_3][^3_1]
2. **Design your own canonical package** in JSONL or SQLite, because you care about long-term portability, deduplication, provenance, and future targets beyond today’s apps.[^3_11]
3. **Create one high-quality Roam JSON parser first**, since Roam JSON is the most workable structured export for migration and downstream transformation.[^3_9]
4. **Generate an Obsidian projection first**, because it is easiest to inspect and diff.
5. **Generate a Logseq file-graph projection second**, and use Logseq’s current import behavior as a validation target.[^3_7][^3_6]
6. **Only then add Logseq DB semantics**, especially for typed properties, tags, and node references, because those require opinionated modeling rather than simple format translation.[^3_12][^3_13]

## Build vs adopt

If your goal were only “get this graph into Obsidian,” I would say adopt an importer directly. But because your goal is a **future-proof migration substrate**, you should build the canonical layer yourself and adopt existing tools only as references, fixtures, or temporary projections.[^3_10]

A good framing is:

- **Adopt** existing conversion logic where it is deterministic and well-tested.
- **Build** the canonical schema, provenance model, dedupe ledger, and adapter pipeline yourself.
- **Benchmark** all outputs against known importers so you can quantify what your pipeline preserves better or differently.

The quickest serious starting point is probably: inspect `obsidian-importer` for fixtures and output patterns, inspect `rj2obs` for block-reference treatment, then implement a minimal canonical parser that round-trips a 25-page pilot corpus into both Obsidian and Logseq-compatible outputs.[^3_14][^3_1][^3_3]

Would you like me to turn this into a concrete starter architecture with a proposed canonical schema, package layout, and adapter interfaces?

<span style="display:none">[^3_15][^3_16][^3_17][^3_18][^3_19][^3_20][^3_21][^3_22][^3_23]</span>

<div align="center">⁂</div>

[^3_1]: https://github.com/obsidianmd/obsidian-importer

[^3_2]: https://github.com/renerocksai/rj2obs

[^3_3]: https://news.ycombinator.com/item?id=26326662

[^3_4]: https://roamdocs.fyi/help/export

[^3_5]: https://marph91.github.io/jimmy/formats/roam_research/

[^3_6]: https://discuss.logseq.com/t/can-i-effectively-import-block-references-from-roam-research-so-they-link-across-pages/4290

[^3_7]: https://nesslabs.com/roam-to-logseq

[^3_8]: https://github.com/logseq/logseq/discussions/7863

[^3_9]: https://www.scribd.com/document/786555307/Lecture-Course-Pentest-english

[^3_10]: https://www.perplexity.ai/search/459b668f-8e88-4d1a-be5b-49b6ebaf3ebc

[^3_11]: https://www.perplexity.ai/search/1d7272ef-64ee-42e2-8261-5da79438ebab

[^3_12]: https://www.academia.edu/129878862/A_Blueprint_for_the_Living_Future

[^3_13]: https://discuss.logseq.com/t/data-structures-for-bridging-logseq-md-to-logseq-db/34851

[^3_14]: https://www.atlasworkspace.ai/blog/roam-research-alternative

[^3_15]: https://forum.obsidian.md/t/my-migration-from-roam-to-obsidian/23221

[^3_16]: https://github.com/avelino/roamresearch-export-block

[^3_17]: https://fabric.so/comparison/logseq-vs-roam-research

[^3_18]: https://github.com/artpi/roam-research-private-api/issues/7

[^3_19]: https://github.com/obsidianmd/obsidian-importer/issues/367

[^3_20]: https://www.reddit.com/r/RoamResearch/comments/1mw5zxv/roam_ai/

[^3_21]: https://www.reddit.com/r/ObsidianMD/comments/kwswon/solution_convert_roam_json_to_obsidian_preserving/

[^3_22]: https://github.com/obsidianmd/obsidian-importer/issues/47

[^3_23]: https://github.com/topics/roamresearch


---

# Yes, show me a concrete starter architecture and schema

Yes — and the right starter architecture is a **canonical graph package plus adapter pipeline**, not a direct “Roam to Obsidian” script. Existing tools prove pieces of the path: Roam JSON exposes pages, nested children, UIDs, strings, and timestamps in a recursively structured export; Obsidian importers and focused converters show practical Markdown projection patterns; and Logseq DB’s Markdown Mirror shows that stable block IDs embedded in Markdown comments are a durable interoperability primitive.[^4_1][^4_2][^4_3]

## System layout

Use four layers:

1. **Raw exports**: untouched Roam JSON, EDN, Markdown, and assets.
2. **Canonical package**: normalized entities, blocks, edges, properties, assets, provenance, and diagnostics.
3. **Adapters**: Obsidian Markdown, classic Logseq Markdown, Logseq DB staging/import format, and future targets.
4. **Validation**: deterministic counts, unresolved references, duplicate candidates, and round-trip audit reports.

A concrete repository layout:

```text
pkm-migrator/
  raw/
    roam/
      graph-a/
        export.json
        export.edn
        export.md.zip
        manifest.json
      graph-b/
        ...
  canonical/
    graphs.jsonl
    pages.jsonl
    blocks.jsonl
    block_order.jsonl
    refs.jsonl
    properties.jsonl
    assets.jsonl
    diagnostics.jsonl
    id_map.jsonl
    duplicate_candidates.jsonl
  adapters/
    obsidian/
    logseq_md/
    logseq_db/
  output/
    obsidian/
    logseq_md/
    logseq_db/
  reports/
    graph-a-summary.json
    graph-a-vs-obsidian.json
    graph-a-vs-logseq.json
```

This separation lets you preserve source fidelity while treating each destination as a projection, not the truth store.[^4_4][^4_5]

## Canonical model

Roam JSON is page-and-block-tree oriented, so the canonical model should normalize that tree into stable node and edge tables while preserving source identity and ordering. Roam exports page titles, children, and timestamps at the page level, and block `uid`, `string`, `children`, and timestamps at the child level.[^4_1]

### Core entities

| Entity | Purpose | Key fields |
| :-- | :-- | :-- |
| `graph` | One imported source graph | `graph_id`, `source_system`, `graph_name`, `exported_at`, `raw_hash` |
| `page` | Logical page/document node | `page_id`, `graph_id`, `source_uid?`, `title`, `normalized_title`, `is_daily_note`, `created_at`, `edited_at` |
| `block` | Atomic content unit | `block_id`, `graph_id`, `source_uid`, `page_id`, `parent_block_id?`, `content_raw`, `content_norm`, `created_at`, `edited_at`, `heading_level?`, `text_align?` |
| `block_order` | Preserves sibling order | `parent_kind`, `parent_id`, `child_block_id`, `position` |
| `ref` | Parsed graph edges | `ref_id`, `source_block_id`, `ref_kind`, `target_page_id?`, `target_block_id?`, `raw_text`, `start_offset`, `end_offset` |
| `property` | Parsed `key:: value` or equivalent | `property_id`, `subject_kind`, `subject_id`, `key`, `value_raw`, `value_type`, `value_norm` |
| `asset` | Files and embedded media | `asset_id`, `source_block_id`, `original_url`, `local_path`, `mime_type`, `hash`, `status` |
| `id_map` | Cross-system identity map | `canonical_id`, `source_system`, `source_graph`, `source_uid`, `destination_system`, `destination_locator` |
| `diagnostic` | Fidelity and parser findings | `severity`, `kind`, `subject_kind`, `subject_id`, `message`, `raw_fragment` |

### Canonical IDs

Make every canonical identifier globally unique and opaque:

```text
graph:roam:graph-a
page:roam:graph-a:2f6d9b3d
block:roam:graph-a:abc123xyz
ref:roam:graph-a:abc123xyz:17
asset:sha256:9f...
```

If Roam page UIDs are absent or inconsistent, generate a stable canonical page ID from `graph_id + normalized_title`, but never discard the original source title history. Roam docs note that UIDs are standard but not fixed-length in principle, so do not build logic that assumes exactly 9 characters.[^4_6]

## Canonical schema

A practical JSON Schema-style shape for the most important records:

```json
{
  "graph": {
    "graph_id": "graph:roam:work",
    "source_system": "roam",
    "graph_name": "Work",
    "exported_at": "2026-09-27T21:00:00Z",
    "raw_hash": "sha256:..."
  },
  "page": {
    "page_id": "page:roam:work:meeting-notes",
    "graph_id": "graph:roam:work",
    "source_uid": null,
    "title": "Meeting Notes",
    "normalized_title": "meeting notes",
    "is_daily_note": false,
    "created_at": "2024-03-10T14:22:00Z",
    "edited_at": "2026-09-01T08:11:00Z"
  },
  "block": {
    "block_id": "block:roam:work:abc123xyz",
    "graph_id": "graph:roam:work",
    "source_uid": "abc123xyz",
    "page_id": "page:roam:work:meeting-notes",
    "parent_block_id": null,
    "content_raw": "Discussed [[Project Atlas]] with ((def456uvw)) #strategy owner:: [[Jane Doe]]",
    "content_norm": "Discussed [[Project Atlas]] with ((def456uvw)) #strategy owner:: [[Jane Doe]]",
    "created_at": "2024-03-10T14:22:00Z",
    "edited_at": "2024-03-12T09:17:00Z",
    "heading_level": null,
    "text_align": null
  }
}
```

And for extracted references and properties:

```json
{
  "ref": {
    "ref_id": "ref:roam:work:abc123xyz:1",
    "source_block_id": "block:roam:work:abc123xyz",
    "ref_kind": "page",
    "target_page_id": "page:roam:work:project-atlas",
    "target_block_id": null,
    "raw_text": "[[Project Atlas]]",
    "start_offset": 10,
    "end_offset": 27
  },
  "property": {
    "property_id": "prop:roam:work:abc123xyz:owner",
    "subject_kind": "block",
    "subject_id": "block:roam:work:abc123xyz",
    "key": "owner",
    "value_raw": "[[Jane Doe]]",
    "value_type": "page_ref",
    "value_norm": "page:roam:work:jane-doe"
  }
}
```


## Parse pipeline

The parser should be multi-phase so you can debug and re-run each step independently.

### Phase 1: ingest

- Store raw exports and compute hashes.
- Parse Roam JSON pages and recursively flatten blocks.
- Convert epoch millisecond timestamps into ISO 8601.
- Preserve every source field, even if the first adapter does not use it. Roam JSON commonly includes timestamps, creator/editor emails, heading markers, and alignment-related fields when present.[^4_7][^4_1]


### Phase 2: normalize

- Build canonical page and block records.
- Create explicit order rows for every child list.
- Infer daily notes from title/UID/date patterns; Roam CLI guidance notes DNP UIDs are date strings in Roam’s model, which is useful as a heuristic but should still be validated against title patterns.[^4_8]
- Normalize line endings, whitespace, and Unicode while keeping `content_raw` untouched.


### Phase 3: extract semantics

Parse and record:

- `[[Page]]` references
- `#tags`
- `((block refs))`
- block embeds
- `key:: value` attributes
- TODO/DONE markers
- dates, URLs, and asset links
- query blocks and unsupported macros

Do not replace inline text destructively during this phase; only annotate it.

### Phase 4: resolve

- Match page refs to canonical pages within the same graph first.
- Resolve block refs by source UID.
- Record unresolved refs explicitly in `diagnostics`.
- Produce duplicate candidates across graphs but do not merge automatically.


## Destination contracts

Each adapter should consume only the canonical package, never raw Roam exports directly.

### Obsidian adapter

Output page-oriented Markdown files with frontmatter and retained block identity.

Suggested note contract:

```markdown
---
source_system: roam
source_graph: work
canonical_page_id: page:roam:work:meeting-notes
roam_page_uid:
created_at: 2024-03-10T14:22:00Z
edited_at: 2026-09-01T08:11:00Z
aliases: []
---

- Discussed [[Project Atlas]] with [[Meeting Notes#^def456uvw]] #strategy
  <!-- canonical:block_id=block:roam:work:abc123xyz -->
  <!-- source:roam_uid=abc123xyz -->
  - owner:: [[Jane Doe]]
```

Important rules:

- Use page-level Markdown notes, not block-per-file.
- Add `^blockid` anchors only for blocks that are referenced elsewhere, mirroring the practical approach taken by `rj2obs`.[^4_3]
- Keep a sidecar `uid-map.jsonl` so broken references can be repaired later.
- Preserve unsupported Roam constructs as fenced source blocks or HTML comments instead of silently dropping them.

Be aware that Obsidian Importer has had block-reference edge cases in some versions, which reinforces why your canonical package should own reference resolution instead of delegating that entirely to the importer.[^4_9]

### Classic Logseq Markdown adapter

Output Logseq-friendly page files and journals with block bullets and properties.

Suggested pattern:

```markdown
title:: Meeting Notes
source-system:: roam
source-graph:: work
canonical-page-id:: page:roam:work:meeting-notes

- Discussed [[Project Atlas]] with ((def456uvw))
  id:: abc123xyz
  canonical-block-id:: block:roam:work:abc123xyz
  - owner:: [[Jane Doe]]
```

Rules:

- Use `journals/YYYY_MM_DD.md` or the date format expected by your chosen Logseq workflow.
- Preserve `id::` for blocks where possible.
- Keep page refs and block refs in Logseq-native syntax when resolvable.
- Emit unresolved refs as explicit placeholders such as `((unresolved:def456uvw))`.


### Logseq DB adapter

Logseq DB is better treated as a **semantic projection**, not just a file conversion target. Its modern Markdown Mirror uses stable IDs embedded in comments so mirrored Markdown survives moves and renames, which is a strong model to emulate in your adapter contract.[^4_2][^4_10]

For now, I would stage Logseq DB through one of two paths:


| Path | When to use | Notes |
| :-- | :-- | :-- |
| Canonical → Logseq Markdown → import to Logseq DB | Safest today | Lets you inspect the intermediate Markdown graph and compare with classic Logseq behavior. [^4_11] |
| Canonical → DB-oriented property/tag staging | Later optimization | Better when you want typed tags, node properties, and schema-aware entities from day one. [^4_12][^4_11] |

For DB-specific modeling, define a translation policy:

- Entity-like pages, such as Person, Project, Company, become typed nodes or tags.
- `key:: value` becomes typed properties when value types are clear.
- Topical tags remain references unless explicitly promoted.
- Block refs become node references only when they target persistent conceptual units rather than incidental prose.


## Example records

A minimally complete set for one block could look like this:

```json
{"page_id":"page:roam:work:meeting-notes","title":"Meeting Notes","graph_id":"graph:roam:work","is_daily_note":false}
{"block_id":"block:roam:work:abc123xyz","source_uid":"abc123xyz","page_id":"page:roam:work:meeting-notes","parent_block_id":null,"content_raw":"Discussed [[Project Atlas]] with ((def456uvw)) #strategy owner:: [[Jane Doe]]","content_norm":"Discussed [[Project Atlas]] with ((def456uvw)) #strategy owner:: [[Jane Doe]]"}
{"ref_id":"ref:1","source_block_id":"block:roam:work:abc123xyz","ref_kind":"page","target_page_id":"page:roam:work:project-atlas","raw_text":"[[Project Atlas]]"}
{"ref_id":"ref:2","source_block_id":"block:roam:work:abc123xyz","ref_kind":"block","target_block_id":"block:roam:work:def456uvw","raw_text":"((def456uvw))"}
{"ref_id":"ref:3","source_block_id":"block:roam:work:abc123xyz","ref_kind":"tag","target_page_id":"page:roam:work:strategy","raw_text":"#strategy"}
{"property_id":"prop:1","subject_kind":"block","subject_id":"block:roam:work:abc123xyz","key":"owner","value_raw":"[[Jane Doe]]","value_type":"page_ref","value_norm":"page:roam:work:jane-doe"}
{"diagnostic_id":"diag:1","severity":"info","kind":"property_extracted","subject_id":"block:roam:work:abc123xyz","message":"Extracted owner property as page reference"}
```


## Validation model

Every run should emit machine-readable checks:

```json
{
  "graph_id": "graph:roam:work",
  "source_counts": {
    "pages": 1240,
    "blocks": 48291,
    "page_refs": 17002,
    "block_refs": 2123,
    "properties": 6310,
    "assets": 418
  },
  "adapter_counts": {
    "obsidian_notes": 1240,
    "obsidian_block_anchors": 2123,
    "unresolved_page_refs": 14,
    "unresolved_block_refs": 37
  }
}
```

Track at least:

- page count
- block count
- child-edge count
- page refs resolved/unresolved
- block refs resolved/unresolved
- property extraction count by type
- assets copied/broken
- duplicate title collisions
- unsupported macro/query count

This gives you objective confidence that a conversion is complete enough to trust.

## Suggested tech stack

A simple implementation stack:

- **Python** for parser and adapters
- **Pydantic** for canonical models
- **SQLite** or JSONL for persisted canonical package
- **Typer** for CLI
- **pytest** with fixture graphs
- Optional **DuckDB** for analysis and duplicate candidate scoring

CLI shape:

```text
pkm migrate ingest raw/roam/graph-a/export.json --graph-id work
pkm migrate normalize --graph-id work
pkm migrate adapt obsidian --graph-id work --out output/obsidian/work
pkm migrate adapt logseq-md --graph-id work --out output/logseq_md/work
pkm migrate report --graph-id work
```


## First implementation slice

Do not build everything first. Start with this vertical slice:

1. Parse one Roam JSON export.
2. Emit `pages.jsonl`, `blocks.jsonl`, `block_order.jsonl`, `refs.jsonl`, and `diagnostics.jsonl`.
3. Support only page refs, block refs, tags, and `key:: value`.
4. Generate Obsidian Markdown with block anchors for referenced blocks only.
5. Generate a validation report comparing source and output counts.
6. Add classic Logseq Markdown second.
7. Add DB-specific promotion rules last.

This is enough to prove the architecture and de-risk the hardest parts: identity, hierarchy, ordering, and reference resolution.[^4_2][^4_3][^4_1]

Would you like me to turn this into an actual starter repo scaffold with concrete folder contents, example JSONL files, and Python model/adapter stubs?

<span style="display:none">[^4_13][^4_14][^4_15][^4_16][^4_17][^4_18]</span>

<div align="center">⁂</div>

[^4_1]: https://davidbieber.com/snippets/2020-04-25-roam-json-export/

[^4_2]: https://discuss.logseq.com/t/whats-new-with-logseq-db-may-16th-2026/35020

[^4_3]: https://github.com/renerocksai/rj2obs

[^4_4]: https://www.perplexity.ai/search/459b668f-8e88-4d1a-be5b-49b6ebaf3ebc

[^4_5]: https://www.perplexity.ai/search/1d7272ef-64ee-42e2-8261-5da79438ebab

[^4_6]: https://roamdocs.fyi/help/json-schema

[^4_7]: https://www.zsolt.blog/2020/12/my-adventures-with-roamjson.html

[^4_8]: https://github.com/forrestchang/roam-research-cli

[^4_9]: https://github.com/obsidianmd/obsidian-importer/issues/247

[^4_10]: https://discuss.logseq.com/t/logseq-db-changelog/30013/37

[^4_11]: https://github.com/logseq/docs/blob/master/db-version.md

[^4_12]: https://discuss.logseq.com/t/data-structures-for-bridging-logseq-md-to-logseq-db/34851

[^4_13]: https://forum.obsidian.md/t/how-to-import-roam-backup-into-obsidian-while-preserving-block-level-references-links/8186

[^4_14]: https://discuss.logseq.com/t/logseq-db-changelog/30013?page=2

[^4_15]: https://discuss.logseq.com/t/is-anyone-planning-to-use-og-version-indefinitely/35091

[^4_16]: https://forum.obsidian.md/t/my-migration-from-roam-to-obsidian/23221

[^4_17]: https://www.reddit.com/r/logseq/comments/1tf8ugh/whats_new_with_logseq_db_may_16_2026/

[^4_18]: https://outl.app/import.html


---

# This is a good start. One other consideration: I'll likely extend this to convert other sources into my cannonical format (Notion, Apple Notes, Google Docs, Obsidian vaults, Logseq DB, ...). We don't need to build them now, but I'd like the canonical data structure to be extendable, versioned, and informed by the broader set of input schemas I'm likely to encounter. What would you change about this plan to accomodate this? What other examples exist that we can learn from or build on?

Yes — I would change the plan in a fairly fundamental way: instead of a Roam-shaped canonical model that other sources are coerced into, make the canonical layer a **versioned document-graph interchange model** with source-specific capability envelopes, typed annotations, and preservation slots for data you cannot yet normalize safely. That is important because Notion is block-plus-property based, Google Docs is structural-element plus style-range based, Apple Notes is note-and-attachment centric with Markdown/ENEX-oriented export paths, and Obsidian/Logseq are file-native Markdown systems with frontmatter, inline fields, and filesystem context.[^7_1][^7_2][^7_3]

## What I would change

The biggest architectural change is to split your canonical package into three layers:

1. **Core semantic layer** — portable entities you expect across many systems: document, block/node, inline span, relation, property, asset, collection, identity, provenance.
2. **Preservation layer** — source-native payload fragments, style spans, unsupported block payloads, and raw schema metadata that you keep even when you cannot yet map them cleanly.
3. **Capability layer** — a machine-readable statement of what the source and each adapter can express, preserve, degrade, or round-trip.

That shift is necessary because Notion exposes both free-form block content and strongly typed page properties, with rich text objects carrying annotations, links, mentions, and equations; Google Docs exposes structural elements such as paragraphs and tables plus paragraph and text styling; and Apple Notes imports/exports Markdown, HTML, RTF, and ENEX-style material with tags and attachments entering the picture differently than in Roam.[^7_2][^7_3][^7_4][^7_5]

## New canonical shape

Instead of centering only on `page`, `block`, and `ref`, I would use these top-level record families:


| Record family | Why it matters | Typical sources |
| :-- | :-- | :-- |
| `package` | Versioning, manifest, migration run metadata | All |
| `source_object` | Raw imported object identity and source-native schema | Roam page/block, Notion page/block/database, Google Doc document/element |
| `document` | Human-facing unit such as note, page, doc, journal entry | Roam page, Notion page, Google Doc, Apple Note, Markdown file |
| `node` | Structural unit in a document tree or graph | Roam block, Notion block, paragraph, list item, table cell |
| `span` | Inline text/rich-text segment with styles and mentions | Notion rich text, Google Docs text runs, Markdown inline formatting |
| `relation` | Explicit or inferred edge between canonical objects | page ref, block ref, mention, property relation, wiki link |
| `attribute` | Key-value metadata at document/node/package scope | YAML frontmatter, Notion properties, Logseq properties |
| `collection` | Containers and schemas | Notion databases, Apple Notes folders, filesystem folders, tags-as-collections |
| `asset` | Attachments and media | images, PDFs, audio, drawings |
| `annotation` | Formatting, comments, suggestions, highlights, status markers | rich text styles, Google Docs suggestions, task markers |
| `provenance_event` | Import, transform, merge, projection, manual review | All |
| `diagnostic` | Loss, ambiguity, unsupported constructs | All |

This structure is better aligned to Notion’s distinction between page content and page properties, where blocks hold narrative content and properties hold structured fields, and to Google Docs’ split between structural elements and their nested paragraph elements or styles.[^7_6][^7_3][^7_7][^7_4]

## Versioning changes

Your package needs **three independent versions**:

- `package_schema_version` — version of the canonical format itself.
- `adapter_contract_version` — version of the output contract for each target.
- `source_profile_version` — version of your mapping logic for each source family, such as `roam@1`, `notion@1`, `gdocs@1`.

That way you can evolve the canonical model without forcing every adapter to change at once. This matters because Notion’s API and block types evolve over time, including newer constructs such as AI meeting notes blocks and rich text variations, and Google Docs’ document model includes multiple structural layers and suggestions that you may not support on day one.[^7_7][^7_4][^7_5]

Example manifest:

```json
{
  "package_id": "pkg_2026_09_27_work",
  "package_schema_version": "0.3.0",
  "source_profiles": [
    {"source_system": "roam", "profile_version": "1.0.0"},
    {"source_system": "notion", "profile_version": "1.0.0"}
  ],
  "adapter_contracts": {
    "obsidian_markdown": "0.2.0",
    "logseq_markdown": "0.2.0",
    "logseq_db": "0.1.0"
  }
}
```


## Preserve richer text and styling

Your current model treats `content_raw` and maybe normalized text as the main content. That will be too lossy for Notion and Google Docs. Notion rich text is explicitly a sequence of objects with `plain_text`, annotations, links, mentions, and equations; some mentions target pages, databases, dates, users, or URLs. Google Docs similarly breaks document content into structural elements, paragraphs, and paragraph elements, including formatting and inline objects.[^7_3][^7_5][^7_7]

So I would add a **span model**:

```json
{
  "span_id": "span:notion:doc1:block1:03",
  "node_id": "node:notion:block1",
  "kind": "text",
  "text": "Project Atlas",
  "marks": ["bold"],
  "link_url": null,
  "mention": {
    "kind": "page",
    "source_object_id": "notion-page-uuid",
    "canonical_target_id": "document:notion:project-atlas"
  },
  "source_range": {"start": 12, "end": 25}
}
```

And a **style/annotation envelope** for block-level styling:

```json
{
  "annotation_id": "ann:gdocs:p17",
  "subject_kind": "node",
  "subject_id": "node:gdocs:p17",
  "annotation_type": "paragraph_style",
  "payload": {
    "named_style": "HEADING_2",
    "alignment": "START"
  }
}
```

This lets you preserve rich text fidelity without overfitting the model to a single Markdown projection.[^7_5][^7_3]

## Add collections and schemas

Notion databases are not just folders; they have explicit property schemas, and page property values conform to those schemas. Apple Notes has account/folder organization and can preserve folder structure on import/export. Obsidian and Logseq depend on filesystem folders, tags, and frontmatter conventions.[^7_2][^7_6]

So I would add:

- `collection` — folder, database, notebook, workspace, vault, journal set.
- `schema_def` — typed definition of attributes for a collection or entity class.
- `membership` — document/node membership in collections.

That enables future Notion database ingestion without flattening everything into plain documents too early.

## Introduce typed relations

Roam-like `[[links]]` are only one kind of relation. Notion mentions can target pages, users, dates, databases, and link previews. Google Docs may have hyperlinks, comments, footnotes, and structural cross-references. So `ref_kind` should evolve into a more expressive relation model:[^7_5]

```json
{
  "relation_id": "rel:notion:block1:page-mention:1",
  "source_id": "node:notion:block1",
  "target_id": "document:notion:project-atlas",
  "relation_type": "mentions",
  "subtype": "page_mention",
  "confidence": 1.0,
  "source_representation": "@Project Atlas"
}
```

Useful top-level relation categories:

- `contains`
- `orders`
- `mentions`
- `links_to`
- `embeds`
- `references`
- `has_property_value`
- `member_of`
- `derived_from`
- `duplicate_of`
- `promoted_to`

This becomes especially valuable if you later add a graph database or retrieval layer on top.[^7_8]

## Distinguish semantic content from rendering

A long-term canonical model should separate:

- **semantic intent**: heading, task, quote, code, callout, table, checklist item, relation property.
- **rendering form**: Markdown bullet, Notion toggle, Google Docs named style, HTML export artifact.

Pandoc is a useful reference here because it uses an AST with metadata plus `Block` and `Inline` elements, explicitly separating document semantics from output rendering. Org mode’s export pipeline is another useful precedent: parse source into an AST, transform the AST, and only then render to a target backend.[^7_9][^7_10][^7_11][^7_12][^7_13][^7_14]

I would therefore add `semantic_kind` and `presentation_hint` separately:

```json
{
  "node_id": "node:gdocs:42",
  "node_type": "paragraph",
  "semantic_kind": "heading",
  "presentation_hint": {
    "source_style": "HEADING_2",
    "preferred_markdown": "##"
  }
}
```


## Add loss accounting to the schema

Right now diagnostics are mostly parser findings. Make them a first-class **fidelity accounting system**:

```json
{
  "fidelity_event_id": "fid:notion:block123",
  "subject_id": "node:notion:block123",
  "source_feature": "rich_text.color",
  "target_system": "obsidian_markdown",
  "status": "degraded",
  "strategy": "preserved_in_annotation",
  "details": "Mapped to inline HTML span in preservation payload, not native Markdown"
}
```

This is especially important because unsupported block types are explicit in the Notion API, and some source systems expose constructs that no Markdown target can represent natively.[^7_4]

## Make identities multi-origin

For future multi-source ingest, one canonical object may have several source identities. A note may originate in Roam, then later also exist in Obsidian and Notion.

So replace one-to-one `id_map` with an identity ledger:

```json
{
  "canonical_id": "document:canon:project-atlas",
  "identities": [
    {"system": "roam", "graph": "work", "object_type": "page", "source_uid": "abc123"},
    {"system": "obsidian", "vault": "main", "path": "Projects/Project Atlas.md"},
    {"system": "notion", "workspace": "team", "page_id": "3c612f56-fdd0-4a30-a4d6-bda7d7426309"}
  ]
}
```

This supports merge histories and later bidirectional sync experiments much better than a single-source map.

## Recommended revised package

A better starter package layout would be:

```text
canonical/
  manifest.json
  package_capabilities.json
  source_profiles/
    roam.json
    notion.json
    gdocs.json
    obsidian.json
    logseq.json
    apple_notes.json
  documents.jsonl
  nodes.jsonl
  spans.jsonl
  relations.jsonl
  attributes.jsonl
  collections.jsonl
  memberships.jsonl
  schemas.jsonl
  assets.jsonl
  identities.jsonl
  annotations.jsonl
  provenance_events.jsonl
  fidelity_events.jsonl
  diagnostics.jsonl
  preservation/
    source-native/
      roam/
      notion/
      gdocs/
```


## Examples to learn from

You asked specifically what examples exist that are worth building on. I would study four categories.

### 1. AST-style interchange models

- **Pandoc AST** is the best conceptual precedent for a versioned intermediate representation that can support many input and output formats. It models documents as metadata plus block and inline structures and supports transformation through filters.[^7_15][^7_9]
- **Org mode export AST** is another strong precedent for parsing source into a tree, transforming it, and only then rendering to backends.[^7_10][^7_13]

These are excellent models for your core semantic layer, though they are more document-centric than graph-centric.

### 2. Rich-content source models

- **Notion API** is useful because it clearly separates page properties from page content, models everything as blocks, and represents inline content as rich text objects with annotations, mentions, equations, and links.[^7_4][^7_5]
- **Google Docs API** is useful because it shows how a richly formatted document can be modeled as structural elements, paragraphs, paragraph elements, tables, and styles.[^7_3][^7_7]

These should influence your `span`, `annotation`, `collection`, and `schema_def` layers.

### 3. PKM migration/import tools

- **Obsidian Importer** is valuable as a projection reference and for test-fixture ideas across multiple proprietary inputs, including Apple Notes and Roam. Apple Notes support in Obsidian Importer explicitly positions conversion toward durable portable Markdown files.[^7_16]
- **rj2obs** remains a good example of block-reference preservation strategy for Roam-to-Obsidian, even though it is too narrow to be the canonical layer.[^7_17]


### 4. Export/import ecosystems with attachments

- **Apple Notes exporter projects** and ENEX-centric workflows are useful because they highlight how attachments, folder structures, and note packaging differ from purely text exports. The Apple Notes exporter example supports Markdown and ENEX outputs and describes how attachments travel either inline or as resources.[^7_18]
- Apple’s own Notes docs matter because they define practical import/export surfaces: Markdown, TXT, RTF, HTML, and ENEX are all plausible interchange entry points for future ingestion.[^7_2]


## Practical design principles

To support future sources cleanly, I would adopt these rules now:

- **Never assume text is a string; model it as spans.** Notion and Google Docs both break that assumption.[^7_3][^7_5]
- **Never assume hierarchy is only page → block.** Notion has pages, blocks, databases, child pages, and typed properties; Google Docs has structural elements and tables.[^7_6][^7_7][^7_4]
- **Never assume metadata is frontmatter-like.** Notion properties are schema-governed; Apple Notes tags and ENEX metadata differ materially.[^7_2][^7_6]
- **Never drop unsupported source data.** Store it in preservation payloads with fidelity events.
- **Version schemas aggressively.** Future you will need migrations.
- **Keep adapters lossy, canonical package loss-minimizing.** That is the core principle.


## What I would do next

I would revise the starter architecture in this order:

1. Add `manifest`, `capabilities`, `source_profile`, `span`, `collection`, `schema_def`, `annotation`, `identities`, and `fidelity_event`.
2. Refactor `page`/`block` into more general `document`/`node`.
3. Keep source-native payloads in a preservation directory for all unsupported or partially mapped constructs.
4. Define a formal compatibility matrix for each source and adapter.
5. Use Roam as the first implemented source, but validate the canonical model against a small synthetic fixture set inspired by Notion blocks, Google Docs paragraphs/tables, Apple Notes attachments, and Markdown/frontmatter.

That gives you a canonical substrate that can grow into a serious multi-source knowledge interchange format instead of becoming “Roam JSON plus some adapters.”

Would you like me to turn this revised design into an explicit JSON Schema and package spec draft?

<span style="display:none">[^7_19][^7_20][^7_21][^7_22][^7_23][^7_24][^7_25][^7_26][^7_27][^7_28][^7_29][^7_30][^7_31][^7_32][^7_33][^7_34]</span>

<div align="center">⁂</div>

[^7_1]: https://developers.notion.com/guides/data-apis/working-with-page-content

[^7_2]: https://support.apple.com/guide/notes/import-export-and-print-notes-not201900c07/mac

[^7_3]: https://developers.google.com/workspace/docs/api/concepts/structure

[^7_4]: https://beepb00p.xyz/myinfra-roam.html

[^7_5]: https://github.com/avelino/roamresearch-export-block

[^7_6]: https://developers.notion.com/reference/property-object

[^7_7]: https://developers.google.com/workspace/docs/api/reference/rest/v1/documents

[^7_8]: https://www.perplexity.ai/search/459b668f-8e88-4d1a-be5b-49b6ebaf3ebc

[^7_9]: https://pandoc.org/filters.html

[^7_10]: https://orgmode.org/manual/Advanced-Export-Configuration.html

[^7_11]: https://pandoc.org/using-the-pandoc-api.html

[^7_12]: https://wiki.tcl-lang.org/page/pandoc

[^7_13]: https://orgmode.org/worg/dev/org-element-api.html

[^7_14]: https://orgmode.org/org.html

[^7_15]: https://pandoc.org/lua-filters.html

[^7_16]: https://obsidian.md/blog/apple-notes-export/

[^7_17]: https://github.com/renerocksai/rj2obs

[^7_18]: https://github.com/kzaremski/apple-notes-exporter

[^7_19]: https://docs.scalekit.com/agentkit/connectors/googledocs/

[^7_20]: https://www.reddit.com/r/Notion/comments/1id4sr2/passing_notion_page_content_through_the/

[^7_21]: https://support.apple.com/en-az/guide/notes/not201900c07/mac

[^7_22]: https://developers.notion.com/reference/rich-text

[^7_23]: https://www.notion.com/blog/creating-the-notion-api

[^7_24]: https://www.seancdavis.com/posts/transform-notion-api-data-into-component-ready-json/

[^7_25]: https://apidog.com/apidoc/docs-site/363296/doc-343618

[^7_26]: https://www.podfeet.com/blog/2025/10/notes-export-as-markdown/

[^7_27]: https://help.noteplan.co/article/33-how-to-import-notes

[^7_28]: https://crates.io/crates/google-docs1

[^7_29]: https://stackoverflow.com/questions/73993468/styling-sections-and-bulleted-lists-via-google-docs-api

[^7_30]: https://cran.r-project.org/web/packages/pandocfilters/pandocfilters.pdf

[^7_31]: https://googleapis.dev/java/google-api-services-docs/latest/com/google/api/services/docs/v1/model/ParagraphStyle.html

[^7_32]: https://pandoc.org/MANUAL.html

[^7_33]: https://orgmode.org/worg/org-tools/index.html

[^7_34]: https://www.rowy.io/blog/google-docs-api


---

# Yes, I agree with this direction and would like to proceed as you have laid out here. And you mentioned the Pandoc tool, which not only is it a good precedent but I actually do think I would like to include it as one of the tools used to export either one or more nodes in this canonical graph to other type of documents that it supports. Since it already has a lot built in, so I probably would want a way to have Pandoc integrate with it anyway, so the more we can learn from that and be consistent, I think is good. I also totally agree that the source may eventually be multi-input because the conversion process will take it from one tool to another, and it will eventually exist in multiple formats. So it'd be good to keep track of that. I am curious what tooling we'll use to version and migrate schema as we proceed. What options do we have? What do you recommend? I also agree modeling as spans rather than strings, since that is going to be more extensible to the various different formats. And I think that there's a reason why that's becoming more common in tooling. So I definitely want to take advantage of the more modern architectures that take these things into consideration since it's more likely it will be extensible. And also if there are any open standards or yeah, standards that could be made to make it easier to integrate with third-party tools, we should consider that because that will allow it to be more easily incorporated into other things. Although I'm sure there's not an open standard for this whole thing, I'm just thinking about maybe portions of it could be done with that. We should definitely plan for the migrations. The versions are going to be very important. So based on all of that, if we could do one more round just to think through the different decisions we need to make around architecture, standards, tooling, migrations, data formats, modeling, things like that, surface as many of those to me as possible. We'll make some decisions and then we'll proceed with the revised design and specifications for this system.

Yes — this is the right moment to slow down and make the architectural decisions explicit. Given your goals, I would treat this as a **versioned canonical interchange system** with three major concerns designed from day one: long-lived schema evolution, multi-source identity and provenance, and multiple projection/export backends including Pandoc-oriented document generation.[^8_1][^8_2]

## Core decisions

The first major decision is what the canonical system is *for*. I would define it as: a durable, source-preserving, semantically normalized interchange layer for note/document/graph systems, designed to ingest heterogeneous sources, retain provenance and unsupported details, and project into downstream tools without making any one tool the authoritative model.[^8_3][^8_4]

That leads to a few architectural consequences:

- The canonical layer should be **loss-minimizing**, while adapters may be lossy.
- The canonical layer should distinguish **semantic structure** from **presentation/rendering**.
- The system should support **multi-origin identity**, since the same conceptual object may later exist in Roam, Obsidian, Notion, and elsewhere.[^8_5][^8_6]


## Model boundaries

I would make five explicit model layers.


| Layer | Purpose | Recommendation |
| :-- | :-- | :-- |
| **Core model** | Documents, nodes, spans, relations, attributes, collections, assets | Keep stable and conservative. |
| **Preservation model** | Source-native payload fragments and unsupported constructs | Required, not optional. |
| **Provenance model** | Where data came from, what transformed it, who reviewed it | Align conceptually with W3C PROV. [^8_2][^8_7] |
| **Capability model** | What each source and adapter can represent or round-trip | Make machine-readable. |
| **Projection model** | Pandoc, Obsidian, Logseq, Logseq DB, future outputs | Separate contracts per target. |

This is better than a single universal schema because Notion pages combine content blocks and typed properties, while Google Docs separates structural elements from paragraph and text styling.[^8_4][^8_8][^8_5]

## Standards to borrow

There is no single open standard for your whole problem, but several standards and de facto models are worth adopting in parts.

### Strong candidates

- **JSON Schema** for canonical document validation and versioned schema files. It is the most practical baseline for your package, compatibility checks, and CI enforcement.[^8_9][^8_10]
- **W3C PROV** for provenance concepts like entity, activity, and agent. You do not need to adopt full PROV-O everywhere, but your provenance model should map cleanly to it.[^8_2][^8_11]
- **JSON-LD** for optional linked-data interoperability, especially if you want stable IDs, graph references, and external tool compatibility later.[^8_12][^8_13]
- **Pandoc AST concepts** for document-like export flows: metadata plus blocks plus inlines is a strong precedent for your document/node/span layer.[^8_1][^8_14]


### Use selectively

- Use **JSON-LD** as an optional serialization surface, not the only native format. Pure JSON/JSONL will be easier for most processing, but JSON-LD contexts can make third-party graph integration easier later.[^8_13][^8_12]
- Use **PROV-inspired terminology** rather than forcing the whole package into raw PROV triples. PROV is a conceptual foundation, not necessarily your storage format.[^8_7][^8_2]


## Pandoc integration

Pandoc should be treated as a **projection engine**, not your canonical model. Pandoc’s AST is document-centric, made of metadata, block elements, and inline elements; it is excellent for exporting selected canonical documents or subtrees into Markdown, DOCX, HTML, PDF, EPUB, and similar formats.[^8_15][^8_1]

I would design a dedicated bridge:

1. Canonical `document/node/span` subset
2. Intermediate **Pandoc projection model**
3. Pandoc AST JSON or Lua-filter pipeline
4. Final output format

That bridge should be intentionally one-way at first. Pandoc is ideal for rendering or converting exportable narrative subsets, but it is not a complete canonical representation for graph semantics like multi-origin identity, source preservation payloads, or PKM-style backlinks.[^8_16][^8_14]

A practical implication is that your canonical model should include a `pandoc_projection` eligibility flag or adapter capability rules:

- Narrative documents, sections, tables, code blocks, quotes, lists, inline emphasis: good Pandoc targets.
- Complex graph-only constructs, unresolved references, source-native schemas, and multi-valued provenance events: preserve separately or emit as appendices/metadata.


## Versioning strategy

You asked specifically about tooling for versioning and migrations. I would use **three layers of versioning**:


| Version type | What it versions | Recommendation |
| :-- | :-- | :-- |
| `schema_version` | Canonical package schema | Semantic versioning. |
| `profile_version` | Source-specific mapping logic, e.g. `roam@1`, `notion@2` | Semantic versioning, separate from package schema. |
| `adapter_version` | Output contract for Obsidian, Pandoc, Logseq, etc. | Semantic versioning per adapter. |

Every record should also carry an in-data marker such as `schemaVersion`, because JSON Schema by itself does not migrate old instances; it only validates them. Best-practice guidance for JSON-style schema evolution consistently emphasizes explicit version markers in data, compatibility contracts, CI checks, and ordered migration functions.[^8_10][^8_17]

### Compatibility modes

Define compatibility *per surface*:

- **Core package**: backward-compatible additive changes by default.
- **Source profiles**: backward-compatible when possible, but may require major versions for remapping semantics.
- **Adapters**: may evolve independently and can tolerate more breakage if clearly versioned.

This follows schema-registry style practice: choose and publish a compatibility contract first, then enforce it in CI.[^8_9][^8_10]

## Migration tooling options

There are several viable approaches.

### Option 1: JSON Schema + code migrations

Use JSON Schema files for validation, plus explicit Python migration scripts for `v0.1 -> v0.2 -> v0.3`.

- **Pros:** Simple, transparent, works well with JSONL/JSON packages.
- **Cons:** You must maintain migration code and tests yourself.

This is my recommendation for your V1.

### Option 2: Avro/Protobuf-style schema registry discipline

Borrow practices from schema registry systems: compatibility checking, defaults for additive fields, aliasing for renamed fields, and CI enforcement.[^8_18][^8_9]

- **Pros:** Strong discipline around evolution.
- **Cons:** The data model is richer and more document-like than classic event schemas, so Avro/Proto themselves are not a natural primary storage model.

Recommendation: use the **discipline**, not necessarily the serialization format.

### Option 3: Database-first migrations

Store canonical records in PostgreSQL or SQLite and version the DB schema using Alembic, Atlas, or similar migration tooling.[^8_19]

- **Pros:** Strong for operational storage.
- **Cons:** Your canonical exchange format should still be file-portable and not depend on a database schema to be understood.

Recommendation: use this only as an implementation/storage layer, not as the public contract.

## My recommendation

For your system, I recommend:

- **Canonical interchange format:** JSONL + manifest JSON.
- **Validation:** JSON Schema.
- **Schema repository:** versioned schema files in Git.
- **Migration engine:** Python migration registry with ordered up-migrations and optional down-migrations.
- **Operational storage:** SQLite or DuckDB mirror, generated from canonical package.
- **CI checks:** schema validation, compatibility tests, fixture migrations, adapter regression tests.

That gives you a docs-as-code style system very similar in spirit to the governance and contract patterns you already prefer.[^8_20]

## Extensibility pattern

I strongly recommend an **extension/facet mechanism** rather than forcing every new concept into the core schema immediately. OpenLineage is a very good precedent here: it has a stable core model plus versioned extensible facets, and custom facets are namespaced and referenced by immutable schema URLs.[^8_21][^8_22][^8_23]

For your system, that could look like:

```json
{
  "document_id": "document:canon:project-atlas",
  "facets": {
    "pkm/source-roam": {
      "_schemaURL": "https://example.org/schemas/facets/source-roam/1-0-0.json",
      "roam_page_uid": "abc123xyz"
    },
    "pkm/pandoc-export": {
      "_schemaURL": "https://example.org/schemas/facets/pandoc-export/1-0-0.json",
      "preferred_template": "briefing"
    }
  }
}
```

This gives you:

- a small, stable core
- source-specific and adapter-specific extensibility
- less schema churn
- future third-party interoperability through published facet schemas[^8_24][^8_21]


## Identity and provenance

Because objects may exist in multiple systems over time, identity should be modeled as a **many-to-one ledger**, not a simple map. Provenance should separately capture what happened to those identities.

A good approach is:

- `canonical_id` for the conceptual object
- one or more `external_identity` records
- `provenance_event` records for ingest, merge, review, projection, and promotion
- optional PROV mapping fields like `entity`, `activity`, `agent`

That mirrors the W3C PROV emphasis on entities, activities, and agents involved in producing or influencing a resource.[^8_2][^8_7]

## Data format decisions

You asked to surface as many architecture and data-format decisions as possible. These are the most important ones.

### Package serialization

- **Option:** single JSON file.
- **Option:** JSONL collection files plus manifest.
- **Recommendation:** JSONL + manifest, because it scales better, diffs better, and supports partial processing.


### Native storage

- **Option:** filesystem only.
- **Option:** DB only.
- **Recommendation:** filesystem canonical package as the contract, with generated SQLite/DuckDB mirrors for query and analysis.


### Text representation

- **Option:** plain strings.
- **Option:** strings plus formatting metadata.
- **Option:** spans/inlines.
- **Recommendation:** spans as the durable content primitive, with convenience materializations like `plain_text` caches.


### Graph representation

- **Option:** implicit links derived from text.
- **Option:** explicit `relation` records.
- **Recommendation:** explicit relations plus source text preservation.


### Schemas

- **Option:** one monolithic schema.
- **Option:** versioned core + facets/extensions.
- **Recommendation:** core + facets.


### Unknown fields

- **Option:** reject unknowns.
- **Option:** allow arbitrary blobs anywhere.
- **Recommendation:** preserve unknowns only in controlled preservation/facet envelopes.


## Migration rules

Adopt these rules from the start:

- Additive changes are preferred.
- New fields should be optional or have defaults when possible.[^8_25][^8_17]
- Avoid renames; introduce new fields and deprecate old ones first.[^8_17][^8_25]
- Never silently change field meaning.
- Every breaking change requires:
    - a major schema version bump
    - migration functions
    - fixture-based regression tests
    - deprecation notes in a changelog[^8_10]

A sound migration workflow would be:

1. Propose schema change.
2. Update JSON Schema files.
3. Add migration function.
4. Run compatibility and fixture tests in CI.
5. Regenerate docs/examples.
6. Migrate stored packages lazily on read or eagerly in batch, depending on risk.[^8_10]

## Candidate toolchain

A practical stack for V1:


| Concern | Recommended tool |
| :-- | :-- |
| Modeling | Python + Pydantic |
| Validation | JSON Schema + `jsonschema` or `fastjsonschema` |
| Migrations | Python migration registry, maybe Alembic-style naming conventions |
| Query mirror | SQLite or DuckDB |
| CLI | Typer |
| Testing | pytest |
| Docs | Markdown spec + generated schema docs |
| Pandoc integration | Pandoc CLI + Lua filters or AST JSON bridge |
| Lint/compat checks | custom CI scripts, possibly `ajv` for schema validation |

## Open integration surfaces

If you want outside tools to integrate more easily, I would publish:

- JSON Schema files for the core and facets.
- A stable `@context` for optional JSON-LD serialization.[^8_12][^8_13]
- A documented Pandoc projection contract.
- A documented provenance contract aligned conceptually to PROV.[^8_2]
- A CLI spec for import/export and schema migration commands.

That gives third parties several levels of entry: simple JSON consumers, linked-data consumers, and document-export consumers.

## Key decisions to make next

Here are the main choices you should probably lock down before writing the revised spec:


| Decision | Options | My recommendation |
| :-- | :-- | :-- |
| Canonical package format | JSON, JSONL, SQLite | JSONL + manifest |
| Schema language | JSON Schema, Avro, Protobuf | JSON Schema |
| Extension model | none, free-form blobs, facets | Versioned facets |
| Provenance model | custom only, PROV-aligned, full PROV-O | PROV-aligned custom model |
| Linked-data support | none, JSON-LD optional, JSON-LD native | JSON-LD optional |
| Migration mechanism | ad hoc scripts, registry-based migrations, DB-only migrations | registry-based code migrations |
| Compatibility policy | none, backward, forward, full by surface | backward-compatible core by default |
| Pandoc role | ignore, canonical model, projection engine | projection engine |
| Query storage | none, Postgres, SQLite/DuckDB mirror | SQLite/DuckDB mirror |
| Identity model | single source map, many-to-one ledger | many-to-one ledger |

## Recommendation set

My recommended architecture, based on everything you said, is:

- **Canonical package:** versioned JSONL + manifest.
- **Model:** document/node/span/relation/attribute/collection/asset/identity/provenance plus preservation and facets.
- **Schema governance:** JSON Schema in Git, semver, migration registry, CI compatibility tests.
- **Extensibility:** OpenLineage-style facets with immutable schema URLs.[^8_23][^8_21]
- **Provenance:** custom model aligned to W3C PROV concepts.[^8_7][^8_2]
- **Linked-data:** optional JSON-LD context for interoperability.[^8_13][^8_12]
- **Document export:** Pandoc as a downstream projection pipeline, not the core model.[^8_1][^8_16]
- **Operational mirrors:** SQLite or DuckDB for analysis and adapter development.

This is the most future-proof path I see that still stays implementable.

The next useful step is to turn this into a decision record set and a draft package spec with explicit fields, versioning rules, compatibility policies, facet conventions, and migration workflow.

<span style="display:none">[^8_26][^8_27][^8_28][^8_29][^8_30][^8_31][^8_32][^8_33][^8_34][^8_35][^8_36]</span>

<div align="center">⁂</div>

[^8_1]: https://pandoc.org/using-the-pandoc-api.html

[^8_2]: https://www.w3.org/TR/2013/WD-prov-dictionary-20130312/

[^8_3]: https://developers.notion.com/guides/data-apis/working-with-page-content

[^8_4]: https://developers.google.com/workspace/docs/api/concepts/structure

[^8_5]: https://beepb00p.xyz/myinfra-roam.html

[^8_6]: https://support.apple.com/guide/notes/import-export-and-print-notes-not201900c07/mac

[^8_7]: https://blogs.ncl.ac.uk/paolomissier/tag/prov-2/

[^8_8]: https://developers.notion.com/reference/property-object

[^8_9]: https://docs.confluent.io/platform/current/schema-registry/fundamentals/schema-evolution.html

[^8_10]: https://www.jundago.com/blog/schema-versioning-strategy

[^8_11]: https://www.w3.org/ns/prov-o.owl

[^8_12]: https://www.w3.org/TR/json-ld11/

[^8_13]: https://w3c.github.io/json-ld-bp/

[^8_14]: https://pandoc.org/filters.html

[^8_15]: https://wiki.tcl-lang.org/page/pandoc

[^8_16]: https://pandoc.org/lua-filters.html

[^8_17]: https://docs.solace.com/Schema-Registry/schema-registry-best-practices.htm

[^8_18]: https://www.confluent.io/blog/best-practices-for-confluent-schema-registry/

[^8_19]: https://atlasgo.io/blog/2024/10/09/strategies-for-reliable-migrations

[^8_20]: https://www.perplexity.ai/search/a1f8c365-618d-469c-9d87-27e7fe6e3a61

[^8_21]: https://openlineage.io/docs/spec/facets/

[^8_22]: https://openlineage.io/docs/spec/schemas/

[^8_23]: https://github.com/OpenLineage/OpenLineage/blob/main/spec/OpenLineage.md

[^8_24]: https://openlineage.io/blog/extending-with-facets/

[^8_25]: https://www.conduktor.io/glossary/schema-evolution-best-practices

[^8_26]: https://openlineage.io/docs/spec/facets/dataset-facets/version_facet/

[^8_27]: https://openlineage.io/docs/1.44.0/spec/facets/dataset-facets/schema/

[^8_28]: https://openlineage.io/docs/1.47.0/spec/facets/dataset-facets/schema

[^8_29]: https://openlineage.io/docs/spec/facets/dataset-facets/storage/

[^8_30]: https://oneuptime.com/blog/post/2026-01-30-kafka-schema-registry-evolution/view

[^8_31]: https://www.w3.org/2005/Incubator/prov/wiki/images/0/02/Provenance-XG-Overview.pdf

[^8_32]: https://pandoc.org/MANUAL.html

[^8_33]: https://linked.art/api/1.0/json-ld/

[^8_34]: https://cran.r-project.org/web/packages/pandocfilters/pandocfilters.pdf

[^8_35]: http://hl7.org/fhir/R4/codesystem-w3c-provenance-activity-type.html

[^8_36]: https://docs.ogc.org/per/24-036.html


---

# turn this into an actual starter repo scaffold with concrete folder contents, example JSONL files, and Python model/adapter stubs

I created a starter repo scaffold as a downloadable zip. It includes a concrete repository layout, JSON Schemas, ADRs, a minimal canonical package with example JSONL files, a Typer CLI, Pydantic models, a migration registry stub, and starter Obsidian plus Pandoc-Markdown adapters.[^10_1][^10_2][^10_3]

## Included structure

The scaffold contains these major areas:

- `specs/` for ADRs, package spec, schemas, and source profiles.
- `examples/minimal-package/` for a working example canonical package with `manifest.json` plus JSONL files for documents, nodes, spans, relations, attributes, identities, provenance, fidelity, diagnostics, collections, and memberships.
- `src/pkmcanon/` for Python code: models, package loading, validation, CLI, migrations, and adapter stubs.
- `tests/` for initial validation and package-loading tests.[^10_2][^10_3]


## What the stubs do

The Python scaffold uses **Pydantic** models for core records and a Typer-based CLI for `validate`, `export`, and `migrate` commands, which is a practical fit for versioned schema-driven tooling in Python. The included adapters currently export a minimal Obsidian Markdown projection and a simple Pandoc-oriented Markdown projection, while leaving room for future direct Pandoc AST or Lua-filter integrations.[^10_4][^10_3][^10_1][^10_2]

## Next decisions

The scaffold is intentionally a V1 foundation rather than a finished implementation. The next high-value steps are to expand the JSON Schemas beyond the manifest/document stub, formalize the facet and preservation record structure, add a Roam ingest pipeline, and define compatibility rules for schema evolution before adding more adapters or sources.[^10_5][^10_6][^10_7]

<span style="display:none">[^10_10][^10_11][^10_12][^10_13][^10_14][^10_15][^10_16][^10_17][^10_18][^10_8][^10_9]</span>

<div align="center">⁂</div>

[^10_1]: https://pandoc.org/lua-filters.html

[^10_2]: https://shiriev.ru/posts/pydantic2/

[^10_3]: https://inventivehq.com/blog/how-to-create-cli-utilities-with-python

[^10_4]: https://pandoc.org/filters.html

[^10_5]: https://docs.confluent.io/platform/current/schema-registry/fundamentals/schema-evolution.html

[^10_6]: https://www.jundago.com/blog/schema-versioning-strategy

[^10_7]: https://github.com/OpenLineage/OpenLineage/blob/main/spec/OpenLineage.md

[^10_8]: https://github.com/fastapi/fastapi/issues/280

[^10_9]: https://mcpmarket.com/zh/tools/skills/python-cli-creator

[^10_10]: https://stackoverflow.com/questions/72352218/python-jsonschema-validation-of-pydantic-class

[^10_11]: https://pkg.yihui.org/rmarkdown-cookbook/lua-filters

[^10_12]: https://gitlab.b-data.ch/jgm/pandoc/-/blob/2.11.1/doc/lua-filters.md

[^10_13]: https://www.zeitkraut.com/posts/2017-12-23-extending-pandoc-with-lua

[^10_14]: https://github.com/jrollin/typer-cli

[^10_15]: https://github.com/pydantic/pydantic/issues/7630

[^10_16]: https://stackoverflow.com/questions/78056160/pandoc-lua-filter-is-there-an-identity-function-example

[^10_17]: https://skills.rest/skill/init-mesca

[^10_18]: https://pypi.org/project/pydantic/2.0.1/


---

I’d expand the schemas by moving from a couple of object stubs to a **modular schema system**: one base envelope schema, one schema per core record type, one schema for shared primitives, and a separate facet/preservation contract that is explicitly extensible and versioned. JSON Schema supports this style well through modular definitions, composition, and controls like `oneOf`, `patternProperties`, and `unevaluatedProperties`.[1][2][3]

## Schema structure

I recommend organizing the schemas into four layers:

| Layer | Purpose | What to put there |
|---|---|---|
| **Meta** | Package-level rules | `manifest.schema.json`, package index, version policy |
| **Primitives** | Reusable field definitions | IDs, timestamps, semantic version, URI, language tags, mark enums |
| **Core records** | Stable canonical entities | document, node, span, relation, attribute, collection, asset, identity, provenance, fidelity, diagnostic |
| **Extensions** | Facets and preservation payloads | base facet schema, facet registry, preservation record schema, source-native payload schemas |

This keeps the core model small and stable while letting source-specific details grow separately, similar to how OpenLineage keeps a minimal core and attaches versioned facets defined by their own JSON Schemas.[4][5]

## Expand the core schemas

The first practical step is to create separate schemas for each major record file, all sharing a common envelope. I would define a `base-record.schema.json` with fields like `record_type`, `schema_version`, `id`, `created_at`, `updated_at`, and optional `facets`, then compose each concrete schema from it with `allOf`. Modular composition is a standard and maintainable pattern for JSON Schema.[2][1]

Suggested first set:

- `document.schema.json`
- `node.schema.json`
- `span.schema.json`
- `relation.schema.json`
- `attribute.schema.json`
- `collection.schema.json`
- `membership.schema.json`
- `asset.schema.json`
- `identity-ledger.schema.json`
- `provenance-event.schema.json`
- `fidelity-event.schema.json`
- `diagnostic.schema.json`

For polymorphic areas, use `oneOf` or `anyOf` deliberately, for example different `span.kind` shapes or different `attribute.value_type` payloads. JSON Schema supports these composition patterns directly.[6][1]

## Shared primitives

You will save a lot of pain by formalizing shared types early. Put these in `defs.schema.json` or `primitives/`:

- Canonical ID
- External identity object
- ISO timestamp
- URI / schema URL
- Semantic version
- Language code
- Mark list for spans, such as bold, italic, code, strike
- Reference target object
- Capability status enum, such as preserved, degraded, unsupported, deferred

This matters because the same fields recur across documents, nodes, facets, provenance events, and identities. Reuse also reduces drift and improves migration reliability.[7][2]

## Facet model

I would formalize facets as **self-contained, versioned metadata units** attached to any core record. The best precedent is OpenLineage: facets are atomic metadata objects with `_schemaURL` and producer metadata, and custom facets use distinct namespaced keys to avoid collisions.[8][9][10]

A good facet contract for you would be:

```json
{
  "pkm/source-roam": {
    "_producer": "https://example.org/pkmcanon",
    "_schemaURL": "https://example.org/pkmcanon/schemas/facets/source-roam/1-0-0.json",
    "roam_page_uid": "abc123xyz",
    "edit_email": "user@example.com"
  }
}
```

### Facet rules

- Every facet must include `_schemaURL`.
- I also recommend `_producer`, following the OpenLineage pattern.[10]
- Facet names should be namespaced, like `pkm/source-roam` or `pkm/pandoc-export`.
- `_schemaURL` should point to an immutable versioned schema location, not a floating branch path. OpenLineage explicitly recommends immutable versioned URLs, ideally tied to a tagged or immutable reference.[9][8]
- Core schemas should allow facets via `patternProperties`, with the actual facet content validated by its own schema. `patternProperties` is designed for exactly this kind of controlled extensibility.[2]

### Base facet schema

Create a `base-facet.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.org/pkmcanon/schemas/base-facet-0.1.0.json",
  "type": "object",
  "required": ["_schemaURL", "_producer"],
  "properties": {
    "_schemaURL": { "type": "string", "format": "uri" },
    "_producer": { "type": "string", "format": "uri" }
  },
  "unevaluatedProperties": true
}
```

Then define concrete facet schemas that extend it with `allOf`. `unevaluatedProperties` is useful here because it lets you compose schemas safely across references and subschemas.[3][2]

## Preservation model

Preservation records should be separate from facets. Facets are for structured, shareable extensions; preservation records are for **loss containment** when the source has constructs you cannot or do not yet normalize cleanly.

I’d create a `preservation-record.schema.json` with fields like:

- `preservation_id`
- `subject_id`
- `source_system`
- `source_object_type`
- `capture_type`, such as `raw_json`, `raw_html`, `rich_text_fragment`, `unsupported_block`
- `content_ref`, such as path or embedded reference
- `mime_type`
- `hash`
- `normalization_status`
- `notes`

Example:

```json
{
  "preservation_id": "preserve:notion:block123",
  "subject_id": "node:canon:meeting-notes:1",
  "source_system": "notion",
  "source_object_type": "block",
  "capture_type": "raw_json",
  "content_ref": "preservation/source-native/notion/block123.json",
  "mime_type": "application/json",
  "hash": "sha256:...",
  "normalization_status": "partial"
}
```

This gives you a formal place to keep raw source payloads without polluting the core record schemas.

## Facets vs preservation

Use this decision rule:

| Use case | Facet | Preservation |
|---|---|---|
| Stable, structured metadata useful across tooling | Yes | No |
| Source-specific metadata you may query later | Usually yes | Maybe |
| Raw unsupported payload | No | Yes |
| Temporary bridge while designing normalization | Maybe | Yes |
| Adapter-specific hint, like Pandoc template preference | Yes | No |

That distinction keeps the extension system clean.

## Validation policy

I would be strict on core records and flexible on extension points.

### Core record policy
- `additionalProperties: false` or `unevaluatedProperties: false` after composition for stable core fields.
- Strong enums where semantics matter.
- Required IDs and version markers everywhere.
- Narrow shape definitions for spans, relations, and provenance.

### Extension policy
- `facets` object should allow namespaced keys via `patternProperties`.
- Each facet must validate against `base-facet`.
- Preservation files should validate against a preservation base schema, but their raw file contents do not need to conform to the canonical model.

This gives you control without blocking extensibility. `unevaluatedProperties` is especially helpful when you want strict validation after applying reusable schema fragments.[3][2]

## File layout

I’d refactor the schema directory like this:

```text
specs/schemas/
  meta/
    manifest.schema.json
    package-index.schema.json
  primitives/
    defs.schema.json
    ids.schema.json
    timestamps.schema.json
    enums.schema.json
  records/
    base-record.schema.json
    document.schema.json
    node.schema.json
    span.schema.json
    relation.schema.json
    attribute.schema.json
    collection.schema.json
    membership.schema.json
    asset.schema.json
    identity-ledger.schema.json
    provenance-event.schema.json
    fidelity-event.schema.json
    diagnostic.schema.json
  facets/
    base-facet.schema.json
    source-roam/
      1-0-0.schema.json
    source-notion/
      1-0-0.schema.json
    pandoc-export/
      1-0-0.schema.json
  preservation/
    preservation-record.schema.json
    source-native-reference.schema.json
```

That structure will age much better than a flat schema directory.

## Concrete next schemas

If you want to expand in the most useful order, I’d do this sequence:

1. `base-record.schema.json`
2. `defs.schema.json`
3. `node.schema.json`
4. `span.schema.json`
5. `relation.schema.json`
6. `identity-ledger.schema.json`
7. `provenance-event.schema.json`
8. `base-facet.schema.json`
9. `preservation-record.schema.json`

That order gets you the hardest and most reused pieces first: structural units, inline content, links, identity, provenance, and extensibility.

## Schema patterns to use

A few specific JSON Schema techniques fit your model well:

- `allOf` for shared envelopes and facet inheritance.[1]
- `oneOf` for record subtypes, such as mention span vs plain text span.[1]
- `anyOf` where you require at least one of several optional identity keys.[6]
- `patternProperties` for namespaced facet keys.[2]
- `unevaluatedProperties: false` after composition to keep core records strict.[3][2]

## Recommendation

My recommendation is:

- Make **core record schemas strict and modular**.
- Make **facets first-class and OpenLineage-inspired**, with `_schemaURL`, `_producer`, namespaced keys, and immutable versioned schema URLs.[8][9][10]
- Make **preservation records explicit**, stored separately from facets and linked by `subject_id`.
- Use `patternProperties` plus `base-facet` to validate extensibility cleanly.[2]
- Keep raw source payloads outside the core record files, referenced through typed preservation records.

The next useful step is to implement these schema files directly in the scaffold and add example records that exercise one facet and one preservation reference end to end.

Sources
[1] Some notes on modular JSON Schema definitions - DJ Adams https://qmacro.org/blog/posts/2022/11/02/some-notes-on-modular-json-schema-definitions/
[2] spec - Litestar Docs https://docs.litestar.dev/main/reference/openapi/spec.html
[3] release-notes.md - json-schema-org/website - GitHub https://github.com/json-schema-org/website/blob/main/pages/draft/2019-09/release-notes.md
[4] Working with Schemas - OpenLineage https://openlineage.io/docs/spec/schemas/
[5] Extending OpenLineage with Facets https://openlineage.io/blog/extending-with-facets/
[6] How to define a JSON schema that requires at least one of many ... https://stackoverflow.com/questions/31839578/how-to-define-a-json-schema-that-requires-at-least-one-of-many-properties
[7] Implementing JSON Schema in TypeScript: Type Inference, Test ... https://imhonglu.github.io/en/1
[8] Facets & Extensibility - OpenLineage https://openlineage.io/docs/spec/facets/
[9] OpenLineage/spec/OpenLineage.md at main - GitHub https://github.com/OpenLineage/OpenLineage/blob/main/spec/OpenLineage.md
[10] Custom Facets - OpenLineage https://openlineage.io/docs/spec/facets/custom-facets/
[11] draft-ietf-jsonschema-json-schema-02 - JSON Schema https://datatracker.ietf.org/doc/draft-ietf-jsonschema-json-schema/02/
[12] Dataset Type Facet - OpenLineage https://openlineage.io/docs/spec/facets/dataset-facets/type/
[13] Schema Dataset Facet - OpenLineage https://openlineage.io/docs/1.44.0/spec/facets/dataset-facets/schema/
[14] Symlinks Facet - OpenLineage https://openlineage.io/docs/spec/facets/dataset-facets/symlinks/
[15] Datasource Facet - OpenLineage https://openlineage.io/docs/spec/facets/dataset-facets/data_source/

---
