import json

import pytest

from pkmcanon.adapters import stable_id
from pkmcanon.models import ReviewPolicy
from pkmcanon.package import PackageValidationError
from pkmcanon.parsers.markdown import MarkdownAdapter
from pkmcanon.products import propose_domain_claims
from pkmcanon.review import (
    ReviewLedger,
    approved_proposals,
    publish_reviewed_domain_page,
)
from pkmcanon.writer import build_package


@pytest.fixture
def review_context(tmp_path):
    """Build an ownership proposal, reviewer policy, and empty filesystem ledger."""
    source = tmp_path / "page.md"
    source.write_text("# Service\n\nOwner: Team\n")
    package = build_package(MarkdownAdapter(), source, tmp_path / "package", source_scope="repo")
    proposal = propose_domain_claims(package)[0]
    policy = ReviewPolicy(policy_version="v1", approved_reviewers=["local-operator", "stranger"])
    return package, proposal, policy, ReviewLedger(tmp_path / "ledger")


@pytest.mark.parametrize("reviewer,decision,code", [
    ("unknown", "approved", "UNAUTHORIZED_REVIEWER"),
    ("stranger", "approved", "REVIEW_ACCESS_DENIED"),
    ("local-operator", "pending", "INVALID_REVIEW_DECISION"),
])
def test_invalid_review_does_not_create_ledger(review_context, reviewer, decision, code):
    """Verify invalid reviewers, access, or decisions fail before creating a ledger."""
    package, proposal, policy, ledger = review_context
    with pytest.raises(PackageValidationError, match=code):
        ledger.record(proposal, package, policy=policy, reviewer_id=reviewer, decision=decision)
    assert ledger.events() == []
    assert not ledger.root.exists()


def test_rejected_claim_cannot_be_published(review_context, tmp_path):
    """Verify a recorded rejection excludes the claim and prevents page publication."""
    package, proposal, policy, ledger = review_context
    event = ledger.record(proposal, package, policy=policy, reviewer_id="local-operator", decision="rejected", rationale="Insufficient evidence")
    assert ledger.events() == [event]
    assert event.rationale == "Insufficient evidence"
    assert approved_proposals([proposal], ledger, policy) == []
    output = tmp_path / "published.md"
    with pytest.raises(PackageValidationError, match="NO_APPROVED_DOMAIN_CLAIMS"):
        publish_reviewed_domain_page(package, [proposal], ledger, policy, output)
    assert not output.exists()


def test_review_replay_keeps_original_bytes_and_policy_cannot_change(review_context):
    """Verify replay preserves the original event and a changed policy cannot rereview it."""
    package, proposal, policy, ledger = review_context
    event = ledger.record(proposal, package, policy=policy, reviewer_id="local-operator", decision="approved", rationale="Original")
    path = ledger.root / f"{event.event_id}.json"
    original = path.read_bytes()
    replay = ledger.record(proposal, package, policy=policy, reviewer_id="local-operator", decision="approved", rationale="Changed")
    assert replay == event
    assert path.read_bytes() == original
    with pytest.raises(PackageValidationError, match="ALREADY_REVIEWED"):
        ledger.record(proposal, package, policy=policy.model_copy(update={"policy_version": "v2"}), reviewer_id="local-operator", decision="approved")
    assert list(ledger.root.iterdir()) == [path]


@pytest.mark.parametrize("tampering", ["filename", "decision", "duplicate"])
def test_ledger_rejects_forged_or_duplicate_decisions(review_context, tampering):
    """Verify event identity checks and duplicate-decision checks detect ledger tampering."""
    package, proposal, policy, ledger = review_context
    event = ledger.record(proposal, package, policy=policy, reviewer_id="local-operator", decision="approved")
    path = ledger.root / f"{event.event_id}.json"
    raw = json.loads(path.read_text())
    code = "REVIEW_EVENT_ID_MISMATCH"
    if tampering == "filename":
        path.rename(ledger.root / "forged.json")
    elif tampering == "decision":
        raw["decision"] = "rejected"
        path.write_text(json.dumps(raw))
    else:
        raw["decision"] = "rejected"
        raw["event_id"] = stable_id("review", proposal.proposal_id, event.reviewer_id, "rejected", policy.policy_version)
        (ledger.root / f"{raw['event_id']}.json").write_text(json.dumps(raw))
        code = "DUPLICATE_REVIEW_DECISION"
    with pytest.raises(PackageValidationError, match=code):
        ledger.events()


def test_approval_from_another_run_cannot_publish(review_context):
    """Verify an approval cannot authorize a proposal with a different run ID."""
    package, proposal, policy, ledger = review_context
    ledger.record(proposal, package, policy=policy, reviewer_id="local-operator", decision="approved")
    with pytest.raises(PackageValidationError, match="REVIEW_RUN_MISMATCH"):
        approved_proposals([proposal.model_copy(update={"run_id": "other-run"})], ledger, policy)
