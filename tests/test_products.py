import json
from pathlib import Path

import pytest

from pkmcanon.evidence import (
    assemble_evidence_bundle,
    evidence_for_node,
    validate_evidence,
)
from pkmcanon.models import ReviewPolicy
from pkmcanon.package import PackageValidationError
from pkmcanon.parsers.markdown import MarkdownAdapter
from pkmcanon.parsers.roam import RoamParser
from pkmcanon.products import (
    propose_domain_claims,
    propose_methodology,
    read_proposals,
    validate_proposal,
    write_proposals,
)
from pkmcanon.review import (
    ReviewLedger,
    publish_methodology,
    publish_reviewed_domain_page,
)
from pkmcanon.review_packet import render_methodology_review_packet
from pkmcanon.shared import project_shared_content
from pkmcanon.writer import build_package


def test_two_adapters_share_boundary_and_review_contract(tmp_path: Path) -> None:
    """Verify both adapters support grounded proposals, authorized review, and publication."""
    roam = tmp_path / "roam.json"
    roam.write_text('[{"uid":"P","title":"Projects","children":[{"uid":"B1","string":"Status:: active"},{"uid":"B2","string":"Status:: planned"}]}]')
    roam_package = build_package(RoamParser(), roam, tmp_path / "roam-package", source_scope="personal")
    methodology = propose_methodology(roam_package)
    assert len(methodology) == 1
    validate_proposal(roam_package, methodology[0])
    methodology_path = tmp_path / "methodology.jsonl"
    write_proposals(methodology_path, methodology)
    assert read_proposals(methodology_path, roam_package) == methodology
    ledger = ReviewLedger(tmp_path / "methodology-reviews")
    policy = ReviewPolicy(policy_version="test-v1", approved_reviewers=["local-operator"])
    unpublished = publish_methodology(roam_package, methodology, ledger, policy, tmp_path / "unpublished.json")
    assert unpublished.rules == []
    with pytest.raises(PackageValidationError, match="UNAUTHORIZED_REVIEWER"):
        ledger.record(methodology[0], roam_package, policy=policy, reviewer_id="stranger", decision="approved")
    event = ledger.record(methodology[0], roam_package, policy=policy, reviewer_id="local-operator", decision="approved")
    assert ledger.record(methodology[0], roam_package, policy=policy, reviewer_id="local-operator", decision="approved") == event
    with pytest.raises(PackageValidationError, match="ALREADY_REVIEWED"):
        ledger.record(methodology[0], roam_package, policy=policy, reviewer_id="local-operator", decision="rejected")
    active = publish_methodology(roam_package, methodology, ledger, policy, tmp_path / "active.json")
    assert len(active.rules) == 1
    assert active.rules[0].source_trace_ids == [item.node_id for item in methodology[0].evidence]
    assert active.review_event_ids == [event.event_id]

    markdown = tmp_path / "context-api.md"
    markdown.write_text("# Context API\n\nOwner: Data Platform\n\nSee [runbook](runbook.md).\n")
    domain_package = build_package(
        MarkdownAdapter(), markdown, tmp_path / "markdown-package",
        source_scope="platform", native_id="docs/context-api.md",
    )
    assert domain_package.documents[0].kind == "markdown"
    assert domain_package.relations[0].target_id == "runbook.md"
    shared = project_shared_content(domain_package)
    assert shared.source_package_id == domain_package.manifest.package_id
    assert shared.items[0].access.visibility == "private"
    assert shared.native_links[0].target_kind == "external"
    claims = propose_domain_claims(domain_package)
    assert len(claims) == 1
    assert claims[0].evidence[0].source_locator.path == "docs/context-api.md"
    assert claims[0].evidence[0].source_locator.line_start == 3
    validate_proposal(domain_package, claims[0])
    domain_ledger = ReviewLedger(tmp_path / "domain-reviews")
    with pytest.raises(PackageValidationError, match="NO_APPROVED_DOMAIN_CLAIMS"):
        publish_reviewed_domain_page(domain_package, claims, domain_ledger, policy, tmp_path / "page.md")
    domain_ledger.record(claims[0], domain_package, policy=policy, reviewer_id="local-operator", decision="approved")
    page = publish_reviewed_domain_page(domain_package, claims, domain_ledger, policy, tmp_path / "page.md")
    assert "Context API" in page and "Data Platform" in page
    assert claims[0].evidence[0].evidence_id in page
    with pytest.raises(PackageValidationError, match="PUBLICATION_ACCESS_DENIED"):
        publish_reviewed_domain_page(domain_package, claims, domain_ledger, policy, tmp_path / "other.md", principal_id="stranger")


def test_context_applies_access_before_retrieval(tmp_path: Path) -> None:
    """Verify inaccessible content contributes no evidence or coverage to a context bundle."""
    source = tmp_path / "doc.md"
    source.write_text("# Service\n\nOwner: Platform Team\n")
    package = build_package(MarkdownAdapter(), source, tmp_path / "package", source_scope="platform")
    allowed = assemble_evidence_bundle(package, "Platform owner", principal_id="local-operator", task_type="ownership")
    denied = assemble_evidence_bundle(package, "Platform owner", principal_id="stranger", task_type="ownership")
    assert allowed.evidence
    assert denied.evidence == []
    assert denied.coverage == "none"


def test_tampered_proposal_evidence_is_rejected(tmp_path: Path) -> None:
    """Verify proposal loading rejects an evidence hash that differs from the source."""
    source = tmp_path / "doc.md"
    source.write_text("# Service\n\nOwner: Platform Team\n")
    package = build_package(MarkdownAdapter(), source, tmp_path / "package", source_scope="platform")
    proposals = propose_domain_claims(package)
    value = proposals[0].model_dump(mode="json")
    value["evidence"][0]["source_content_hash"] = "0" * 64
    path = tmp_path / "tampered.jsonl"
    path.write_text(json.dumps(value) + "\n")
    with pytest.raises(PackageValidationError, match="PROPOSAL_INVALID"):
        read_proposals(path, package)


def test_evidence_can_preserve_an_unknown_start_offset(tmp_path: Path) -> None:
    source = tmp_path / "doc.md"
    source.write_text("# Service\n\nOwner: Platform Team\n")
    package = build_package(MarkdownAdapter(), source, tmp_path / "package", source_scope="platform")
    node = next(item for item in package.nodes if "Owner:" in item.plain_text)
    evidence = evidence_for_node(package, node.node_id, start=None, end=5)
    assert evidence.start is None
    assert evidence.end == 5
    assert evidence.quote == "Owner"
    validate_evidence(package, evidence)


def test_publication_rejects_decisions_under_a_different_policy(tmp_path: Path) -> None:
    source = tmp_path / "doc.md"
    source.write_text("# Service\n\nOwner: Platform Team\n")
    package = build_package(MarkdownAdapter(), source, tmp_path / "package", source_scope="platform")
    proposals = propose_domain_claims(package)
    policy = ReviewPolicy(policy_version="v1", approved_reviewers=["local-operator"])
    ledger = ReviewLedger(tmp_path / "reviews")
    ledger.record(proposals[0], package, policy=policy, reviewer_id="local-operator", decision="approved")
    changed_policy = ReviewPolicy(policy_version="v2", approved_reviewers=["local-operator"])
    with pytest.raises(PackageValidationError, match="REVIEW_POLICY_MISMATCH"):
        publish_reviewed_domain_page(package, proposals, ledger, changed_policy, tmp_path / "page.md")


def test_markdown_partial_structure_has_preserved_payload(tmp_path: Path) -> None:
    """Verify a partially normalized table retains its source text and preservation link."""
    source = tmp_path / "table.md"
    source.write_text("# Table\n\n| A | B |\n| - | - |\n| 1 | 2 |\n")
    package = build_package(MarkdownAdapter(), source, tmp_path / "package", source_scope="platform")
    assert package.manifest.fidelity.partial == 1
    assert package.diagnostics[0].preservation_id == package.preservation_records[0].id
    assert package.preservation_records[0].storage.inline_utf8 == source.read_text()


def test_code_example_does_not_become_domain_claim(tmp_path: Path) -> None:
    """Verify an Owner line inside a code example produces no ownership proposal."""
    source = tmp_path / "example.md"
    source.write_text("# Example\n\n~~~\nOwner: Fictional Team\n~~~\n")
    package = build_package(MarkdownAdapter(), source, tmp_path / "package", source_scope="platform")
    assert package.manifest.fidelity.partial == 1
    assert propose_domain_claims(package) == []


@pytest.fixture
def methodology_package(tmp_path):
    source = tmp_path / "rules.json"
    source.write_text(json.dumps([{"uid": "P", "title": "Rules", "children": [
        {"uid": str(i), "string": "Status:: active"} for i in range(8)
    ]}]))
    return build_package(RoamParser(), source, tmp_path / "package", source_scope="graph")


def test_methodology_groups_evidence_without_treating_repeated_blocks_as_independent_support(methodology_package):
    """Count distinct supporting pages while preserving citations and access checks."""
    proposals = propose_methodology(methodology_package)
    assert len(proposals) == 1
    proposal = proposals[0]
    assert len(proposal.evidence) == 8
    assert proposal.confidence == proposal.payload["confidence"] == 0.61
    assert proposal.payload["distinct_document_count"] == 1
    assert proposal.payload["substantive_value_count"] == 8
    assert proposal.payload["statement"].startswith("For Roam graph graph, consider using Status::")
    assert proposal.payload["status"] == proposal.status == "proposed"
    assert proposal.payload["source_trace_ids"] == sorted(node.node_id for node in methodology_package.nodes)
    assert propose_methodology(methodology_package, principal_id="stranger") == []
    validate_proposal(methodology_package, proposal)


def test_methodology_defers_blank_templates_and_surfaces_scope_variants_and_cooccurrence(tmp_path):
    source = tmp_path / "templates.json"
    source.write_text(json.dumps([
        {"uid": "P1", "title": "One", "children": [
            {"uid": "B1", "string": "Command:: "},
            {"uid": "B2", "string": "command:: TBD"},
            {"uid": "B3", "string": "Status:: active"},
            {"uid": "B4", "string": "Status:: planned"},
        ]},
        {"uid": "P2", "title": "Two", "children": [
            {"uid": "B5", "string": "COMMAND:: <value>"},
            {"uid": "B6", "string": "status:: done"},
        ]},
        {"uid": "P3", "title": "Three", "children": [
            {"uid": "B7", "string": "Status:: active"},
            {"uid": "B8", "string": "Status:: active"},
        ]},
    ]))
    package = build_package(RoamParser(), source, tmp_path / "package", source_scope="graph")
    proposals = propose_methodology(package)
    assert len(proposals) == 2
    by_key = {item.payload["key_variants"][0].casefold(): item for item in proposals}
    command = by_key["command"]
    assert command.payload["observation_count"] == 3
    assert command.payload["distinct_document_count"] == 2
    assert command.payload["blank_value_count"] == 1
    assert command.payload["placeholder_value_count"] == 2
    assert command.payload["substantive_value_count"] == 0
    assert command.payload["key_variants"] == ["COMMAND", "Command", "command"]
    assert command.payload["cooccurring_keys"] == {"Status": 2}
    assert command.payload["review_priority"] == "defer"
    assert command.confidence == 0
    status = by_key["status"]
    assert status.payload["distinct_document_count"] == 3
    assert status.payload["cooccurring_keys"] == {"Command": 2}
    assert status.payload["review_priority"] == "review"
    assert status.confidence > command.confidence
    assert all(item.status == "proposed" for item in proposals)
    assert all(len(item.evidence) == item.payload["observation_count"] for item in proposals)
    packet = render_methodology_review_packet(proposals)
    assert "1 deferred for weak or template-like support" in packet
    assert packet.index("Status::") < packet.index("Command::")
    assert "support heuristic" in packet


@pytest.mark.parametrize("field,value,code", [
    ("source_package_id", "other", "PROPOSAL_PACKAGE_MISMATCH"),
    ("status", "approved", "INVALID_PROPOSAL_STATUS"),
    ("payload_schema", "other", "PROPOSAL_SCHEMA_MISMATCH"),
    ("confidence", 0.1, "PROPOSAL_CONFIDENCE_MISMATCH"),
    ("proposal_type", "documentation_change", "UNSUPPORTED_PROPOSAL_TYPE"),
])
def test_proposal_validation_rejects_inconsistent_envelopes(methodology_package, field, value, code):
    proposal = propose_methodology(methodology_package)[0].model_copy(update={field: value})
    with pytest.raises(PackageValidationError, match=code):
        validate_proposal(methodology_package, proposal)


@pytest.mark.parametrize("update,code", [
    ({"status": "approved"}, "INVALID_PROPOSAL_STATUS"),
    ({"source_trace_ids": ["absent"]}, "PROPOSAL_TRACE_MISMATCH"),
])
def test_proposal_validation_checks_payload_status_and_traces(methodology_package, update, code):
    proposal = propose_methodology(methodology_package)[0]
    proposal = proposal.model_copy(update={"payload": {**proposal.payload, **update}})
    with pytest.raises(PackageValidationError, match=code):
        validate_proposal(methodology_package, proposal)


def test_proposal_file_is_immutable_and_duplicate_ids_are_rejected(methodology_package, tmp_path):
    proposals = propose_methodology(methodology_package)
    path = tmp_path / "nested" / "proposals.jsonl"
    write_proposals(path, proposals)
    original = path.read_bytes()
    write_proposals(path, proposals)
    assert path.read_bytes() == original
    with pytest.raises(PackageValidationError, match="PROPOSALS_EXIST"):
        write_proposals(path, [])
    assert path.read_bytes() == original
    path.write_bytes(b"\n" + original + b"\n")
    assert read_proposals(path, methodology_package) == proposals
    path.write_bytes(original + original)
    with pytest.raises(PackageValidationError, match="DUPLICATE_PROPOSAL"):
        read_proposals(path, methodology_package)
    path.write_text("\n{bad json}\n")
    with pytest.raises(PackageValidationError, match="PROPOSAL_INVALID: line 2"):
        read_proposals(path, methodology_package)
