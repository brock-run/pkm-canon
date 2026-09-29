"""Rebuildable lexical and native-link projections over canonical packages."""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from pathlib import Path

from .adapters import stable_id
from .evidence import can_access, evidence_for_node
from .models import EvidenceBundle, IndexProjection, NativeLink
from .package import CanonicalPackage, PackageValidationError
from .schema_validation import default_schema_store

PROFILE_VERSION = "lexical-graph-v1"


def _terms(text: str) -> set[str]:
    return {term.lower() for term in re.findall(r"[A-Za-z0-9_]+", text) if len(term) > 2}


def build_index(package: CanonicalPackage) -> IndexProjection:
    terms: dict[str, list[str]] = defaultdict(list)
    for node in package.nodes:
        for term in sorted(_terms(node.plain_text)):
            terms[term].append(node.node_id)
    links = [
        NativeLink(
            link_id=item.relation_id, source_id=item.source_id,
            target_id=item.target_id, kind=item.relation_type,
            target_kind=item.target_kind, source_representation=item.source_representation,
        )
        for item in package.relations
    ]
    index = IndexProjection(
        index_id=stable_id("index", package.manifest.package_id, PROFILE_VERSION),
        source_package_id=package.manifest.package_id,
        profile_version=PROFILE_VERSION,
        terms={key: sorted(set(value)) for key, value in sorted(terms.items())},
        native_links=sorted(links, key=lambda item: item.link_id),
    )
    default_schema_store().validate_instance_with_short_name(index.model_dump(mode="json"), "index-projection")
    return index


def write_index(package: CanonicalPackage, output: Path) -> IndexProjection:
    index = build_index(package)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text(
        json.dumps(index.model_dump(mode="json", exclude_none=True), sort_keys=True, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, output)
    return index


def load_index(package: CanonicalPackage, path: Path) -> IndexProjection:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    default_schema_store().validate_instance_with_short_name(raw, "index-projection")
    index = IndexProjection.model_validate(raw)
    if index != build_index(package):
        raise PackageValidationError("INDEX_STALE_OR_TAMPERED", str(path))
    return index


def search_index(
    package: CanonicalPackage, index: IndexProjection, query: str, *,
    principal_id: str, task_type: str, limit: int = 8,
) -> EvidenceBundle:
    if index.source_package_id != package.manifest.package_id:
        raise PackageValidationError("INDEX_PACKAGE_MISMATCH", index.index_id)
    terms = _terms(query)
    scores: dict[str, int] = defaultdict(int)
    for term in terms:
        for node_id in index.terms.get(term, []):
            scores[node_id] += 1
    nodes = {item.node_id: item for item in package.nodes}
    docs = {item.document_id: item for item in package.documents}
    sources = {item.source_version_id: item for item in package.manifest.source_versions}
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    evidence = []
    for node_id, _ in ranked:
        if len(evidence) >= max(0, limit):
            break
        node = nodes[node_id]
        source = sources[docs[node.document_id].source_version_id]
        if can_access(source, principal_id):
            evidence.append(evidence_for_node(package, node_id))
    covered = {term for item in evidence for term in terms if term in _terms(item.quote or "")}
    coverage = "none" if not evidence else ("complete" if covered == terms else "partial")
    return EvidenceBundle(
        bundle_id=stable_id("ctx", index.index_id, principal_id, task_type, query),
        source_package_id=package.manifest.package_id,
        requester_principal_id=principal_id, task_type=task_type, query=query,
        retrieval_profile_version=index.profile_version, evidence=evidence, coverage=coverage,
    )


def related_content_ids(
    package: CanonicalPackage, index: IndexProjection, source_id: str, *,
    principal_id: str,
) -> list[str]:
    if index.source_package_id != package.manifest.package_id:
        raise PackageValidationError("INDEX_PACKAGE_MISMATCH", index.index_id)
    nodes = {item.node_id: item for item in package.nodes}
    docs = {item.document_id: item for item in package.documents}
    sources = {item.source_version_id: item for item in package.manifest.source_versions}

    def allowed(identifier: str) -> bool:
        doc = docs.get(identifier)
        if doc is None:
            node = nodes.get(identifier)
            doc = docs[node.document_id] if node else None
        return bool(doc and can_access(sources[doc.source_version_id], principal_id))

    if not allowed(source_id):
        return []
    return sorted({
        link.target_id for link in index.native_links
        if link.source_id == source_id and link.target_kind == "canonical" and allowed(link.target_id)
    })
