"""Two product plugins over the same evidence and proposal contracts."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from .adapters import stable_id
from .evidence import can_access, evidence_for_node, validate_evidence
from .models import DomainClaim, MethodologyRule, Proposal, RetrievalChange
from .package import CanonicalPackage, PackageValidationError
from .schema_validation import default_schema_store

RULE_SCHEMA = "urn:pkm-canon:schema:v1:knowledge:methodology-rule"
CLAIM_SCHEMA = "urn:pkm-canon:schema:v1:knowledge:domain-claim"
RETRIEVAL_SCHEMA = "urn:pkm-canon:schema:v1:knowledge:retrieval-change"
OWNER = re.compile(r"^Owner:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
PLACEHOLDER = re.compile(r"^(?:\.{2,}|-+|<[^<>]+>|(?:your|insert|enter|add|fill in)\b.*\b(?:here|name|value|text))$", re.IGNORECASE)
PLACEHOLDER_WORDS = {"tbd", "todo", "n/a", "na", "none", "placeholder", "example", "sample"}


def _value_quality(value: object) -> str:
    """Classify only obvious empty/template values; uncertain values remain substantive."""
    text = str(value).strip()
    if not text:
        return "blank"
    if text.casefold() in PLACEHOLDER_WORDS or PLACEHOLDER.fullmatch(text):
        return "placeholder"
    return "substantive"


def propose_methodology(package: CanonicalPackage, *, principal_id: str = "local-operator") -> list[Proposal]:
    """Propose source-scoped attribute rules from accessible, cited observations.

    Return one proposal per key with document support and a transparent value-
    quality heuristic; proposals are neither persisted nor approved here.
    """
    if not package.manifest.source_versions:
        return []
    docs = {item.document_id: item for item in package.documents}
    nodes = {item.node_id: item for item in package.nodes}
    sources = {item.source_version_id: item for item in package.manifest.source_versions}
    source_scope = package.manifest.source_versions[0].source_scope
    attributes: dict[str, list[tuple[str, str, str, object]]] = defaultdict(list)
    document_keys: dict[str, set[str]] = defaultdict(set)
    for attribute in package.attributes:
        if attribute.subject_id not in nodes:
            continue
        document = docs[nodes[attribute.subject_id].document_id]
        if can_access(sources[document.source_version_id], principal_id):
            key = attribute.key.strip().casefold()
            if key:
                attributes[key].append((attribute.subject_id, document.document_id, attribute.key, attribute.value))
                document_keys[document.document_id].add(key)
    variants = {key: Counter(row[2] for row in rows) for key, rows in attributes.items()}
    display_keys = {key: max(counts, key=counts.get) for key, counts in variants.items()}
    run_id = stable_id("run", package.manifest.package_id, "methodology-v2")
    proposals = []
    for key, rows in sorted(attributes.items()):
        node_ids = sorted({row[0] for row in rows})
        evidence = [evidence_for_node(package, node_id) for node_id in node_ids]
        documents = {row[1] for row in rows}
        quality = Counter(_value_quality(row[3]) for row in rows)
        substantive_docs = {row[1] for row in rows if _value_quality(row[3]) == "substantive"}
        observations = len(rows)
        substantive = quality["substantive"]
        score = round(
            0.45 * substantive / observations
            + 0.4 * min(len(substantive_docs), 5) / 5
            + 0.1 * min(substantive, 10) / 10,
            2,
        )
        cooccurrence = Counter(other for doc_id in documents for other in document_keys[doc_id] if other != key)
        cooccurring_keys = {
            display_keys[other]: count
            for other, count in sorted(cooccurrence.items(), key=lambda item: (-item[1], display_keys[item[0]]))[:5]
        }
        priority = "defer" if substantive < 2 or substantive * 2 < observations else "review"
        rule = MethodologyRule(
            rule_id=stable_id("rule", package.manifest.package_id, "attribute-v2", key),
            rule_type="attribute_convention",
            statement=(
                f"For Roam graph {source_scope}, consider using {display_keys[key]}:: as a block attribute; "
                f"observed in {len(evidence)} block(s) across {len(documents)} page(s)."
            ),
            confidence=score,
            source_trace_ids=[item.node_id for item in evidence],
            source_scope=source_scope,
            observation_count=observations,
            distinct_document_count=len(documents),
            substantive_value_count=substantive,
            blank_value_count=quality["blank"],
            placeholder_value_count=quality["placeholder"],
            key_variants=sorted(variants[key]),
            cooccurring_keys=cooccurring_keys,
            review_priority=priority,
        )
        proposals.append(Proposal(
            proposal_id=stable_id("prop", package.manifest.package_id, rule.rule_id),
            proposal_type="methodology_rule", payload_schema=RULE_SCHEMA,
            payload=rule.model_dump(mode="json"), evidence=evidence,
            confidence=rule.confidence, source_package_id=package.manifest.package_id, run_id=run_id,
        ))
    return proposals


def propose_domain_claims(package: CanonicalPackage, *, principal_id: str = "local-operator") -> list[Proposal]:
    """Draft ownership claims from accessible Markdown Owner lines outside code nodes."""
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
    """Validate proposal identity, payload, status, trace IDs, and source-grounded evidence."""
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
    """Write proposals in stable ID order, rejecting an existing file with different content."""
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
    """Load JSONL proposals and validate their schemas, evidence, and unique IDs."""
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
