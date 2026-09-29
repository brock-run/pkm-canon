# Repository Markdown source profile 0.1.0

The adapter packages one UTF-8 Markdown file as a versioned source snapshot.
Source scope identifies the repository; `native_id` is its repository-relative
path. The raw file is retained and hashed in the package.

- One `Document` represents the file. Its title is the first Markdown heading,
  or the path if no heading exists.
- Headings and nonempty paragraph blocks become `Node` records, with source
  line ranges in a namespaced facet. Each node has a full-text `Span`.
- Markdown links become native `Relation` records with
  `target_kind=external`. A relative link is recorded as written; this adapter
  does not resolve it against other packages.
- Tables, fenced code, front matter, and HTML remain in the raw text and are
  flagged as partially normalized, with a preservation record and diagnostic.
- IDs derive from source system, repository scope, file path, and source line.
  Identical bytes and input identity yield identical records. Line insertion
  can change block IDs; exact evidence remains tied to the immutable source
  version.

The first product plugin recognizes an explicit `Owner: Team Name` line and
proposes an evidence-linked `owned_by` domain claim. It does not infer
ownership from arbitrary prose. Publication requires a separate review event.
