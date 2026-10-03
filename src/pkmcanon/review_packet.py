"""Read-only local preview of evidence-grounded methodology proposals."""

from __future__ import annotations

from html import escape

from .models import MethodologyRule, Proposal


def render_methodology_review_packet(
    proposals: list[Proposal], *, evidence_limit: int = 3,
    decisions: dict[str, str] | None = None,
) -> str:
    """Render escaped proposal and evidence previews without recording decisions."""
    if evidence_limit < 1:
        raise ValueError("evidence_limit must be positive")
    ordered = sorted(proposals, key=lambda item: (-len(item.evidence), item.proposal_id))
    style = (
        '<style>body{font:16px/1.5 system-ui,sans-serif;max-width:900px;margin:3rem auto;padding:0 1rem;color:#18202a}'
        'article{border-top:1px solid #c9d0d7;padding:1.2rem 0}h1,h2{line-height:1.2}'
        'h2{font-size:1.15rem}code,pre{white-space:pre-wrap;overflow-wrap:anywhere}'
        'blockquote{border-left:3px solid #b3bfca;margin:1rem 0;padding:.2rem 1rem;background:#f5f7f8}'
        '.meta{color:#53606b}details{margin:.7rem 0}</style></head><body>'
    )
    parts = [
        '<!doctype html><html lang="en"><head><meta charset="utf-8">',
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">',
        '<title>Rosetta methodology review</title>',
        style,
        f'<h1>Methodology review queue</h1><p>{len(ordered)} proposed rules, ranked by supporting evidence.</p>',
        '<p>Decisions come from the review ledger when provided. Evidence below is a preview; inspect the full source before approving a rule.</p>',
    ]
    for proposal in ordered:
        rule = MethodologyRule.model_validate(proposal.payload)
        decision = (decisions or {}).get(proposal.proposal_id, "unreviewed")
        parts.extend([
            '<article>',
            f'<h2>{escape(rule.statement)}</h2>',
            f'<p class="meta">Decision: {escape(decision)} · {len(proposal.evidence)} evidence block(s) · confidence {proposal.confidence:.2f} · <code>{escape(proposal.proposal_id)}</code></p>',
            f'<details><summary>Preview {min(len(proposal.evidence), evidence_limit)} citation(s)</summary>',
        ])
        for evidence in proposal.evidence[:evidence_limit]:
            place = evidence.source_locator.path or evidence.source_locator.source_uid or "source"
            quote = evidence.quote or ""
            preview = quote[:350] + ("…" if len(quote) > 350 else "")
            parts.append(f'<blockquote><p>{escape(preview)}</p><p class="meta"><code>{escape(place)}</code></p></blockquote>')
        parts.append('</details></article>')
    parts.append('</body></html>')
    return "".join(parts)
