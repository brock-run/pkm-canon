"""Source-neutral content projection over a validated Rosetta package."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .models import ContentElement, ContentItem, NativeLink, SharedContentSnapshot
from .package import CanonicalPackage
from .schema_validation import default_schema_store


def project_shared_content(package: CanonicalPackage) -> SharedContentSnapshot:
    sources = {item.source_version_id: item for item in package.manifest.source_versions}
    snapshot = SharedContentSnapshot(
        contract_version="0.1.0",
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
                position=node.position, text=node.plain_text,
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
