"""Append-only review decisions and approved knowledge projections."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from .adapters import stable_id
from .evidence import can_access
from .models import (
    DomainClaim,
    MethodologyManifest,
    MethodologyRule,
    Proposal,
    ReviewEvent,
    ReviewPolicy,
)
from .package import CanonicalPackage, PackageValidationError
from .products import validate_proposal
from .schema_validation import default_schema_store


def _json(model) -> str:
    """Serialize a model as sorted, indented JSON, omitting None fields."""
    return json.dumps(model.model_dump(mode="json", exclude_none=True), sort_keys=True, ensure_ascii=False, indent=2) + "\n"


def load_review_policy(path: Path) -> ReviewPolicy:
    """Load a review policy and validate it against the schema and runtime model."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    default_schema_store().validate_instance_with_short_name(raw, "review-policy")
    return ReviewPolicy.model_validate(raw)


class ReviewLedger:
    def __init__(self, root: Path):
        """Store the directory used for immutable review-event files."""
        self.root = Path(root)

    def events(self) -> list[ReviewEvent]:
        """Load review events, checking their identities and rejecting repeated proposal decisions."""
        if not self.root.exists():
            return []
        events = []
        decided = set()
        for path in sorted(self.root.glob("*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            default_schema_store().validate_instance_with_short_name(raw, "review-event")
            event = ReviewEvent.model_validate(raw)
            if path.stem != event.event_id:
                raise PackageValidationError("REVIEW_EVENT_ID_MISMATCH", str(path))
            expected_id = stable_id(
                "review", event.proposal_id, event.reviewer_id,
                event.decision, event.policy_version,
            )
            if event.event_id != expected_id:
                raise PackageValidationError("REVIEW_EVENT_ID_MISMATCH", str(path))
            if event.proposal_id in decided:
                raise PackageValidationError("DUPLICATE_REVIEW_DECISION", event.proposal_id)
            decided.add(event.proposal_id)
            events.append(event)
        return events

    def record(
        self, proposal: Proposal, package: CanonicalPackage, *,
        policy: ReviewPolicy, reviewer_id: str, decision: str, rationale: str | None = None,
    ) -> ReviewEvent:
        """Record an authorized decision, reusing an identical review and rejecting conflicting decisions."""
        validate_proposal(package, proposal)
        if reviewer_id not in policy.approved_reviewers:
            raise PackageValidationError("UNAUTHORIZED_REVIEWER", reviewer_id)
        sources = {item.source_version_id: item for item in package.manifest.source_versions}
        if any(not can_access(sources[item.source_version_id], reviewer_id) for item in proposal.evidence):
            raise PackageValidationError("REVIEW_ACCESS_DENIED", reviewer_id)
        if decision not in {"approved", "rejected"}:
            raise PackageValidationError("INVALID_REVIEW_DECISION", decision)
        existing = next((item for item in self.events() if item.proposal_id == proposal.proposal_id), None)
        if existing is not None:
            if existing.reviewer_id == reviewer_id and existing.decision == decision and existing.policy_version == policy.policy_version:
                return existing
            raise PackageValidationError("ALREADY_REVIEWED", proposal.proposal_id)
        event = ReviewEvent(
            event_id=stable_id("review", proposal.proposal_id, reviewer_id, decision, policy.policy_version),
            proposal_id=proposal.proposal_id, reviewer_id=reviewer_id,
            run_id=proposal.run_id, decision=decision,
            decided_at=datetime.now(UTC).isoformat(),
            rationale=rationale, policy_version=policy.policy_version,
        )
        default_schema_store().validate_instance_with_short_name(event.model_dump(mode="json", exclude_none=True), "review-event")
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root / f"{event.event_id}.json"
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.root, prefix=".review-", delete=False) as stream:
            stream.write(_json(event))
            temporary = Path(stream.name)
        try:
            os.link(temporary, target)  # atomic create; never overwrite an event
        except FileExistsError as exc:
            raise PackageValidationError("REVIEW_EVENT_EXISTS", str(target)) from exc
        finally:
            temporary.unlink(missing_ok=True)
        return event


def approved_proposals(proposals: list[Proposal], ledger: ReviewLedger) -> list[tuple[Proposal, ReviewEvent]]:
    """Pair approved proposals with ledger events after checking that their run IDs match."""
    events = {item.proposal_id: item for item in ledger.events()}
    for proposal in proposals:
        event = events.get(proposal.proposal_id)
        if event is not None and event.run_id != proposal.run_id:
            raise PackageValidationError("REVIEW_RUN_MISMATCH", proposal.proposal_id)
    return [
        (proposal, events[proposal.proposal_id])
        for proposal in proposals
        if proposal.proposal_id in events and events[proposal.proposal_id].decision == "approved"
    ]


def publish_methodology(
    package: CanonicalPackage, proposals: list[Proposal], ledger: ReviewLedger, output: Path,
) -> MethodologyManifest:
    """Validate approved methodology rules and atomically publish their manifest."""
    selected = []
    for proposal, event in approved_proposals(proposals, ledger):
        if proposal.proposal_type != "methodology_rule":
            continue
        validate_proposal(package, proposal)
        rule = MethodologyRule.model_validate(proposal.payload).model_copy(update={"status": "approved"})
        selected.append((rule, event))
    selected.sort(key=lambda item: item[0].rule_id)
    manifest = MethodologyManifest(
        manifest_id=stable_id("methodology", package.manifest.package_id, *(item.rule_id for item, _ in selected)),
        source_package_id=package.manifest.package_id,
        rules=[item for item, _ in selected],
        review_event_ids=[event.event_id for _, event in selected],
        generated_at=datetime.now(UTC).isoformat(),
    )
    default_schema_store().validate_instance_with_short_name(manifest.model_dump(mode="json"), "methodology-manifest")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text(_json(manifest), encoding="utf-8")
    os.replace(temporary, output)
    return manifest


def publish_reviewed_domain_page(
    package: CanonicalPackage, proposals: list[Proposal], ledger: ReviewLedger,
    output: Path, *, principal_id: str = "local-operator",
) -> str:
    """Publish approved domain claims with evidence, requiring access to every cited source."""
    sources = {item.source_version_id: item for item in package.manifest.source_versions}
    selected = []
    for proposal, event in approved_proposals(proposals, ledger):
        if proposal.proposal_type != "domain_claim":
            continue
        validate_proposal(package, proposal)
        for evidence in proposal.evidence:
            if not can_access(sources[evidence.source_version_id], principal_id):
                raise PackageValidationError("PUBLICATION_ACCESS_DENIED", evidence.evidence_id)
        selected.append((DomainClaim.model_validate(proposal.payload), proposal, event))
    if not selected:
        raise PackageValidationError("NO_APPROVED_DOMAIN_CLAIMS", package.manifest.package_id)
    selected.sort(key=lambda item: item[0].claim_id)
    lines = [
        "---",
        "status: reviewed",
        f"source_package_id: {package.manifest.package_id}",
        f"claim_count: {len(selected)}",
        "---",
        "",
        "# Reviewed domain claims",
        "",
    ]
    for claim, proposal, event in selected:
        lines.extend([
            f"## {claim.subject}",
            "",
            f"- **{claim.predicate.replace('_', ' ')}:** {claim.object}",
            f"- Reviewed by: {event.reviewer_id} ({event.decided_at})",
            f"- Review event: {event.event_id}",
            "",
            "Evidence:",
            "",
        ])
        for evidence in proposal.evidence:
            locator = evidence.source_locator
            place = locator.path or locator.source_uid or evidence.node_id
            if locator.line_start is not None:
                place += f":{locator.line_start}"
            lines.append(f"- {evidence.evidence_id} · {evidence.source_version_id} · {place}: {evidence.quote}")
        lines.append("")
    content = "\n".join(lines)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, output)
    return content
