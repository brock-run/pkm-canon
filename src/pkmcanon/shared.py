"""Source-neutral content projection over a validated PKM Canon package."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .models import (
    ContentElement,
    ContentItem,
    NativeLink,
    Node,
    SharedContentSnapshot,
    SourceLocator,
)
from .package import CanonicalPackage
from .schema_validation import default_schema_store


def project_shared_content(package: CanonicalPackage) -> SharedContentSnapshot:
    """Project documents, nodes, and links into a schema-validated shared content snapshot.

    Include Markdown or Roam source locators when applicable, leaving missing
    facet details unset. Preserve access policies without filtering content.
    Model and JSON Schema validation errors and schema-loading errors propagate
    to the caller; no snapshot is written to disk.
    """
    sources = {item.source_version_id: item for item in package.manifest.source_versions}
    documents = {item.document_id: item for item in package.documents}

    def locator_for(node: Node) -> SourceLocator | None:
        """Build a Markdown or Roam source locator, or return None for other sources."""
        document = documents[node.document_id]
        source = sources[document.source_version_id]
        if document.kind == "markdown":
            facet = node.facets.get("pkm/source-markdown")
            details = (facet.model_extra or {}) if facet else {}
            return SourceLocator(
                workspace=source.source_scope, path=source.native_id,
                line_start=details.get("line_start"), line_end=details.get("line_end"),
            )
        if source.source_system == "roam":
            facet = node.facets.get("pkm/source-roam")
            details = (facet.model_extra or {}) if facet else {}
            roam_uid = details.get("roam_uid")
            return SourceLocator(
                graph=source.source_scope, path=details.get("json_pointer"),
                source_uid=roam_uid if isinstance(roam_uid, str) else None,
            )
        return None

    snapshot = SharedContentSnapshot(
        contract_version="0.2.0",
        source_package_id=package.manifest.package_id,
        source_versions=package.manifest.source_versions,
        items=[
            ContentItem(
                item_id=doc.document_id, source_version_id=doc.source_version_id,
                kind=doc.kind, title=doc.title,
                source_event_time=doc.updated_at or doc.created_at,
                observed_at=sources[doc.source_version_id].observed_at,
                access=sources[doc.source_version_id].access,
            )
            for doc in package.documents
        ],
        elements=[
            ContentElement(
                element_id=node.node_id, item_id=node.document_id,
                parent_element_id=node.parent_node_id, kind=node.semantic_kind or node.node_type,
                position=node.position, text=node.plain_text, source_locator=locator_for(node),
            )
            for node in package.nodes
        ],
        native_links=[
            NativeLink(
                link_id=relation.relation_id, source_id=relation.source_id,
                target_id=relation.target_id, kind=relation.relation_type,
                target_kind=relation.target_kind,
                source_representation=relation.source_representation,
            )
            for relation in package.relations
        ],
    )
    default_schema_store().validate_instance_with_short_name(snapshot.model_dump(mode="json"), "content-snapshot")
    return snapshot


def write_shared_content(package: CanonicalPackage, output: Path) -> SharedContentSnapshot:
    """Atomically write a shared content snapshot as JSON and return it."""
    snapshot = project_shared_content(package)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text(
        json.dumps(snapshot.model_dump(mode="json", exclude_none=True), sort_keys=True, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, output)
    return snapshot
