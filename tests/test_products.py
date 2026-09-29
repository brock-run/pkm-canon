import json
from pathlib import Path

import pytest

from pkmcanon.evidence import assemble_evidence_bundle
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
from pkmcanon.shared import project_shared_content
from pkmcanon.writer import build_package


def test_two_adapters_share_boundary_and_review_contract(tmp_path: Path) -> None:
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
    unpublished = publish_methodology(roam_package, methodology, ledger, tmp_path / "unpublished.json")
    assert unpublished.rules == []
    policy = ReviewPolicy(policy_version="test-v1", approved_reviewers=["local-operator"])
    with pytest.raises(PackageValidationError, match="UNAUTHORIZED_REVIEWER"):
        ledger.record(methodology[0], roam_package, policy=policy, reviewer_id="stranger", decision="approved")
    event = ledger.record(methodology[0], roam_package, policy=policy, reviewer_id="local-operator", decision="approved")
    assert ledger.record(methodology[0], roam_package, policy=policy, reviewer_id="local-operator", decision="approved") == event
    with pytest.raises(PackageValidationError, match="ALREADY_REVIEWED"):
        ledger.record(methodology[0], roam_package, policy=policy, reviewer_id="local-operator", decision="rejected")
    active = publish_methodology(roam_package, methodology, ledger, tmp_path / "active.json")
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
        publish_reviewed_domain_page(domain_package, claims, domain_ledger, tmp_path / "page.md")
    domain_ledger.record(claims[0], domain_package, policy=policy, reviewer_id="local-operator", decision="approved")
    page = publish_reviewed_domain_page(domain_package, claims, domain_ledger, tmp_path / "page.md")
    assert "Context API" in page and "Data Platform" in page
    assert claims[0].evidence[0].evidence_id in page
    with pytest.raises(PackageValidationError, match="PUBLICATION_ACCESS_DENIED"):
        publish_reviewed_domain_page(domain_package, claims, domain_ledger, tmp_path / "other.md", principal_id="stranger")


def test_context_applies_access_before_retrieval(tmp_path: Path) -> None:
    source = tmp_path / "doc.md"
    source.write_text("# Service\n\nOwner: Platform Team\n")
    package = build_package(MarkdownAdapter(), source, tmp_path / "package", source_scope="platform")
    allowed = assemble_evidence_bundle(package, "Platform owner", principal_id="local-operator", task_type="ownership")
    denied = assemble_evidence_bundle(package, "Platform owner", principal_id="stranger", task_type="ownership")
    assert allowed.evidence
    assert denied.evidence == []
    assert denied.coverage == "none"


def test_tampered_proposal_evidence_is_rejected(tmp_path: Path) -> None:
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


def test_markdown_partial_structure_has_preserved_payload(tmp_path: Path) -> None:
    source = tmp_path / "table.md"
    source.write_text("# Table\n\n| A | B |\n| - | - |\n| 1 | 2 |\n")
    package = build_package(MarkdownAdapter(), source, tmp_path / "package", source_scope="platform")
    assert package.manifest.fidelity.partial == 1
    assert package.diagnostics[0].preservation_id == package.preservation_records[0].id
    assert package.preservation_records[0].storage.inline_utf8 == source.read_text()


def test_code_example_does_not_become_domain_claim(tmp_path: Path) -> None:
    source = tmp_path / "example.md"
    source.write_text("# Example\n\n~~~\nOwner: Fictional Team\n~~~\n")
    package = build_package(MarkdownAdapter(), source, tmp_path / "package", source_scope="platform")
    assert package.manifest.fidelity.partial == 1
    assert propose_domain_claims(package) == []
