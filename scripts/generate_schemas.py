"""Generate or check portable JSON Schemas from the runtime models."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pkmcanon import models

SCHEMAS = {
    "core/documents.schema.json": models.Document,
    "core/nodes.schema.json": models.Node,
    "core/spans.schema.json": models.Span,
    "core/relations.schema.json": models.Relation,
    "core/attributes.schema.json": models.Attribute,
    "core/facet-envelope.schema.json": models.FacetEnvelope,
    "common/source-native-reference.schema.json": models.SourceNativeReference,
    "common/source-version.schema.json": models.SourceVersion,
    "shared/content-item.schema.json": models.ContentItem,
    "shared/content-element.schema.json": models.ContentElement,
    "shared/native-link.schema.json": models.NativeLink,
    "shared/content-snapshot.schema.json": models.SharedContentSnapshot,
    "preservation/preservation-record.schema.json": models.PreservationRecord,
    "preservation/preservation-bundle.schema.json": models.PreservationBundle,
    "package/manifest.schema.json": models.Manifest,
    "package/diagnostic.schema.json": models.Diagnostic,
    "knowledge/evidence-ref.schema.json": models.EvidenceRef,
    "knowledge/evidence-bundle.schema.json": models.EvidenceBundle,
    "knowledge/methodology-rule.schema.json": models.MethodologyRule,
    "knowledge/domain-claim.schema.json": models.DomainClaim,
    "knowledge/retrieval-change.schema.json": models.RetrievalChange,
    "evaluation/evaluation-case.schema.json": models.EvaluationCase,
    "evaluation/evaluation-result.schema.json": models.EvaluationResult,
    "knowledge/proposal.schema.json": models.Proposal,
    "knowledge/review-policy.schema.json": models.ReviewPolicy,
    "knowledge/review-event.schema.json": models.ReviewEvent,
    "knowledge/methodology-manifest.schema.json": models.MethodologyManifest,
    "projection/projection-manifest.schema.json": models.ProjectionManifest,
    "projection/index-projection.schema.json": models.IndexProjection,
}


def _source_reference_constraints(schema: dict) -> None:
    """Mirror SourceNativeReference's cross-field runtime validation."""
    locator = {
        "relative_path": "relative_path",
        "embedded_utf8": "inline_utf8",
        "embedded_base64": "inline_base64",
        "external_uri": "external_uri",
    }
    schema["allOf"] = [
        {
            "if": {"properties": {"storage_kind": {"const": kind}}, "required": ["storage_kind"]},
            "then": {
                "required": [field],
                "properties": {
                    field: {"type": "string", "minLength": 1},
                    **{other: {"type": "null"} for other in locator.values() if other != field},
                },
            },
        }
        for kind, field in locator.items()
    ]


def _augment_source_references(schema: dict, *, root_is_reference: bool = False) -> None:
    """Add storage-locator constraints to root and nested source-reference schemas."""
    if root_is_reference:
        _source_reference_constraints(schema)
    for name, definition in schema.get("$defs", {}).items():
        if name == "SourceNativeReference":
            _source_reference_constraints(definition)


def rendered_schema(path: str, model: type) -> str:
    """Render a model schema with stable identifiers and source-reference constraints."""
    schema = model.model_json_schema(by_alias=True)
    _augment_source_references(schema, root_is_reference=model is models.SourceNativeReference)
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = f"urn:pkm-canon:schema:v1:{path.removesuffix('.schema.json').replace('/', ':')}"
    schema["title"] = path.removesuffix(".schema.json").split("/")[-1]
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    """Generate committed schemas, or return a nonzero status when --check finds drift."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if committed schemas are stale")
    args = parser.parse_args()
    schema_root = ROOT / "docs" / "specs" / "schemas"
    stale = []
    for relative, model in SCHEMAS.items():
        path = schema_root / relative
        desired = rendered_schema(relative, model)
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != desired:
                stale.append(relative)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(desired, encoding="utf-8")
    if stale:
        print("Stale schemas: " + ", ".join(stale), file=sys.stderr)
        return 1
    if not args.check:
        print(f"Generated {len(SCHEMAS)} schemas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
