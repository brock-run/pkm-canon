"""Source-version-grounded evidence and access-aware context assembly."""

from __future__ import annotations

import re

from .adapters import stable_id
from .models import EvidenceBundle, EvidenceRef, SourceLocator, SourceVersion
from .package import CanonicalPackage, PackageValidationError


def can_access(source: SourceVersion, principal_id: str) -> bool:
    """Return whether the source is public or explicitly grants the principal access."""
    if source.access.visibility == "public":
        return True
    return principal_id in source.access.principal_ids


def evidence_for_node(
    package: CanonicalPackage, node_id: str, *,
    start: int = 0, end: int | None = None,
) -> EvidenceRef:
    """Build source-grounded evidence for a node character range, rejecting invalid bounds."""
    node = next((item for item in package.nodes if item.node_id == node_id), None)
    if node is None:
        raise PackageValidationError("DANGLING_EVIDENCE_NODE", node_id)
    document = next(item for item in package.documents if item.document_id == node.document_id)
    source = next(item for item in package.manifest.source_versions if item.source_version_id == document.source_version_id)
    end = len(node.plain_text) if end is None else end
    if not (0 <= start <= end <= len(node.plain_text)):
        raise PackageValidationError("INVALID_EVIDENCE_RANGE", node_id)
    span = next((item for item in package.spans if item.node_id == node_id and item.start == 0 and item.end == len(node.plain_text)), None)
    if document.kind == "markdown":
        facet = node.facets.get("pkm/source-markdown")
        details = (facet.model_extra or {}) if facet else {}
        locator = SourceLocator(
            workspace=source.source_scope, path=source.native_id,
            line_start=details.get("line_start"), line_end=details.get("line_end"),
            char_start=start, char_end=end,
        )
    else:
        facet = node.facets.get("pkm/source-roam")
        details = (facet.model_extra or {}) if facet else {}
        locator = SourceLocator(
            graph=source.source_scope, path=details.get("json_pointer"),
            source_uid=details.get("roam_uid"), char_start=start, char_end=end,
        )
    return EvidenceRef(
        evidence_id=stable_id("ev", document.source_version_id, node_id, str(start), str(end)),
        source_version_id=document.source_version_id,
        source_locator=locator, source_content_hash=source.content_hash,
        node_id=node_id, span_id=span.span_id if span else None,
        start=start, end=end, quote=node.plain_text[start:end],
    )


def validate_evidence(package: CanonicalPackage, evidence: EvidenceRef) -> None:
    """Reject evidence that differs from the reference reconstructed from the package."""
    expected = evidence_for_node(
        package, evidence.node_id,
        start=evidence.start or 0, end=evidence.end,
    )
    if evidence != expected:
        raise PackageValidationError("EVIDENCE_MISMATCH", evidence.evidence_id)


def assemble_evidence_bundle(
    package: CanonicalPackage, query: str, *,
    principal_id: str, task_type: str, limit: int = 8,
) -> EvidenceBundle:
    """Rank accessible nodes by query-term matches and report evidence coverage."""
    terms = {term.lower() for term in re.findall(r"[A-Za-z0-9_]+", query) if len(term) > 2}
    sources = {item.source_version_id: item for item in package.manifest.source_versions}
    docs = {item.document_id: item for item in package.documents}
    ranked = []
    for node in package.nodes:
        source = sources[docs[node.document_id].source_version_id]
        if not can_access(source, principal_id):
            continue
        lowered = node.plain_text.lower()
        score = sum(term in lowered for term in terms)
        if score:
            ranked.append((score, node.node_id))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    evidence = [evidence_for_node(package, node_id) for _, node_id in ranked[:max(0, limit)]]
    covered = {term for item in evidence for term in terms if term in (item.quote or "").lower()}
    coverage = "none" if not evidence else ("complete" if covered == terms else "partial")
    return EvidenceBundle(
        bundle_id=stable_id("ctx", package.manifest.package_id, principal_id, task_type, query, "lexical-v1"),
        source_package_id=package.manifest.package_id, requester_principal_id=principal_id,
        task_type=task_type, query=query, retrieval_profile_version="lexical-v1",
        evidence=evidence, coverage=coverage,
    )
