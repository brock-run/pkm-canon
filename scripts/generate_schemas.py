from __future__ import annotations
import json
from pathlib import Path
from pkmcanon.models import Document, Node, Span, Relation, Attribute, FacetEnvelope

SCHEMA_ROOT = Path("specs/schemas/core")
SCHEMA_ROOT.mkdir(parents=True, exist_ok=True)

MODELS = {
    "documents.schema.json": (Document, "https://example.org/schemas/core/documents", "documents"),
    "nodes.schema.json": (Node, "https://example.org/schemas/core/nodes", "nodes"),
    "spans.schema.json": (Span, "https://example.org/schemas/core/spans", "spans"),
    "relations.schema.json": (Relation, "https://example.org/schemas/core/relations", "relations"),
    "attributes.schema.json": (Attribute, "https://example.org/schemas/core/attributes", "attributes"),
    "facet-envelope.schema.json": (FacetEnvelope, "https://example.org/schemas/core/facet-envelope", "facet-envelope"),
}

for filename, (model, schema_id, title) in MODELS.items():
    schema = model.model_json_schema(by_alias=True)
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = schema_id
    schema["title"] = title
    (SCHEMA_ROOT / filename).write_text(json.dumps(schema, indent=2), encoding="utf-8")
    print(f"wrote {filename}")
