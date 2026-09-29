"""Two product plugins over the same evidence and proposal contracts."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from .adapters import stable_id
from .evidence import can_access, evidence_for_node, validate_evidence
from .models import DomainClaim, MethodologyRule, Proposal, RetrievalChange
from .package import CanonicalPackage, PackageValidationError
from .schema_validation import default_schema_store

RULE_SCHEMA = "urn:pkm-rosetta:schema:v1:knowledge:methodology-rule"
CLAIM_SCHEMA = "urn:pkm-rosetta:schema:v1:knowledge:domain-claim"
RETRIEVAL_SCHEMA = "urn:pkm-rosetta:schema:v1:knowledge:retrieval-change"
OWNER = re.compile(r"^Owner:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)


def propose_methodology(package: CanonicalPackage, *, principal_id: str = "local-operator") -> list[Proposal]:
    docs = {item.document_id: item for item in package.documents}
    nodes = {item.node_id: item for item in package.nodes}
    sources = {item.source_version_id: item for item in package.manifest.source_versions}
    attributes: dict[str, list[str]] = defaultdict(list)
    for attribute in package.attributes:
        if attribute.subject_id not in nodes:
            continue
        document = docs[nodes[attribute.subject_id].document_id]
        if can_access(sources[document.source_version_id], principal_id):
            attributes[attribute.key].append(attribute.subject_id)
    run_id = stable_id("run", package.manifest.package_id, "methodology-v1")
    proposals = []
    for key, node_ids in sorted(attributes.items()):
        evidence = [evidence_for_node(package, node_id) for node_id in sorted(set(node_ids))]
        rule = MethodologyRule(
            rule_id=stable_id("rule", package.manifest.package_id, "attribute", key),
            rule_type="attribute_convention",
            statement=f"Consider using {key}:: as a block attribute; observed in {len(evidence)} block(s).",
            confidence=min(0.95, 0.4 + 0.1 * len(evidence)),
            source_trace_ids=[item.node_id for item in evidence],
        )
        proposals.append(Proposal(
            proposal_id=stable_id("prop", package.manifest.package_id, rule.rule_id),
            proposal_type="methodology_rule", payload_schema=RULE_SCHEMA,
            payload=rule.model_dump(mode="json"), evidence=evidence,
            confidence=rule.confidence, source_package_id=package.manifest.package_id, run_id=run_id,
        ))
    return proposals


def propose_domain_claims(package: CanonicalPackage, *, principal_id: str = "local-operator") -> list[Proposal]:
    docs = {item.document_id: item for item in package.documents}
    sources = {item.source_version_id: item for item in package.manifest.source_versions}
    run_id = stable_id("run", package.manifest.package_id, "domain-claims-v1")
    proposals = []
    for node in package.nodes:
        document = docs[node.document_id]
        if document.kind != "markdown" or node.semantic_kind == "code" or not can_access(sources[document.source_version_id], principal_id):
            continue
        for match in OWNER.finditer(node.plain_text):
            evidence = evidence_for_node(package, node.node_id, start=match.start(), end=match.end())
            claim = DomainClaim(
                claim_id=stable_id("claim", package.manifest.package_id, document.document_id, "owned_by", match.group(1)),
                subject=document.title, predicate="owned_by", object=match.group(1),
                source_trace_ids=[node.node_id],
            )
            proposals.append(Proposal(
                proposal_id=stable_id("prop", package.manifest.package_id, claim.claim_id),
                proposal_type="domain_claim", payload_schema=CLAIM_SCHEMA,
                payload=claim.model_dump(mode="json"), evidence=[evidence], confidence=0.8,
                source_package_id=package.manifest.package_id, run_id=run_id,
            ))
    return proposals


def validate_proposal(package: CanonicalPackage, proposal: Proposal) -> None:
    if proposal.source_package_id != package.manifest.package_id:
        raise PackageValidationError("PROPOSAL_PACKAGE_MISMATCH", proposal.proposal_id)
    if proposal.status != "proposed":
        raise PackageValidationError("INVALID_PROPOSAL_STATUS", proposal.proposal_id)
    if proposal.proposal_type == "methodology_rule":
        if proposal.payload_schema != RULE_SCHEMA:
            raise PackageValidationError("PROPOSAL_SCHEMA_MISMATCH", proposal.proposal_id)
        payload = MethodologyRule.model_validate(proposal.payload)
        schema_name = "methodology-rule"
    elif proposal.proposal_type == "domain_claim":
        if proposal.payload_schema != CLAIM_SCHEMA:
            raise PackageValidationError("PROPOSAL_SCHEMA_MISMATCH", proposal.proposal_id)
        payload = DomainClaim.model_validate(proposal.payload)
        schema_name = "domain-claim"
    elif proposal.proposal_type == "retrieval_change":
        if proposal.payload_schema != RETRIEVAL_SCHEMA:
            raise PackageValidationError("PROPOSAL_SCHEMA_MISMATCH", proposal.proposal_id)
        payload = RetrievalChange.model_validate(proposal.payload)
        schema_name = "retrieval-change"
    else:
        raise PackageValidationError("UNSUPPORTED_PROPOSAL_TYPE", proposal.proposal_type)
    default_schema_store().validate_instance_with_short_name(proposal.payload, schema_name)
    if payload.status != "proposed":
        raise PackageValidationError("INVALID_PROPOSAL_STATUS", proposal.proposal_id)
    if isinstance(payload, MethodologyRule) and payload.confidence != proposal.confidence:
        raise PackageValidationError("PROPOSAL_CONFIDENCE_MISMATCH", proposal.proposal_id)
    if set(payload.source_trace_ids) != {item.node_id for item in proposal.evidence}:
        raise PackageValidationError("PROPOSAL_TRACE_MISMATCH", proposal.proposal_id)
    for evidence in proposal.evidence:
        validate_evidence(package, evidence)


def write_proposals(path: Path, proposals: list[Proposal]) -> None:
    path = Path(path)
    content = "".join(
        json.dumps(item.model_dump(mode="json"), sort_keys=True, ensure_ascii=False) + "\n"
        for item in sorted(proposals, key=lambda item: item.proposal_id)
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise PackageValidationError("PROPOSALS_EXIST", str(path))
        return
    with path.open("x", encoding="utf-8") as stream:
        stream.write(content)


def read_proposals(path: Path, package: CanonicalPackage) -> list[Proposal]:
    proposals = []
    ids = set()
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
            default_schema_store().validate_instance_with_short_name(raw, "proposal")
            proposal = Proposal.model_validate(raw)
            validate_proposal(package, proposal)
        except Exception as exc:
            raise PackageValidationError("PROPOSAL_INVALID", f"line {number}: {exc}") from exc
        if proposal.proposal_id in ids:
            raise PackageValidationError("DUPLICATE_PROPOSAL", proposal.proposal_id)
        ids.add(proposal.proposal_id)
        proposals.append(proposal)
    return proposals
