"""Local operator commands for package generation and validation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer

from .evaluation import (
    evaluate_retrieval,
    propose_retrieval_changes,
    read_evaluation_cases,
    write_evaluation_results,
)
from .evidence import assemble_evidence_bundle
from .index import load_index, search_index, write_index
from .jobs import JobStore, create_app
from .package import CanonicalPackage, PackageValidationError
from .parsers.markdown import MarkdownAdapter
from .parsers.roam import RoamParser
from .products import (
    propose_domain_claims,
    propose_methodology,
    read_proposals,
    validate_proposal,
    write_proposals,
)
from .projection import project_audit_markdown
from .review import (
    ReviewLedger,
    load_review_policy,
    publish_methodology,
    publish_reviewed_domain_page,
)
from .shared import write_shared_content
from .writer import build_package

app = typer.Typer(no_args_is_help=True)


def _summary(package: CanonicalPackage) -> str:
    return json.dumps({
        "package_id": package.manifest.package_id,
        "source_versions": [item.source_version_id for item in package.manifest.source_versions],
        "fidelity": package.manifest.fidelity.model_dump(),
        "record_counts": {
            name: entry.record_count for name, entry in package.manifest.files.items()
            if entry.record_count is not None
        },
    }, sort_keys=True)


@app.command("ingest-roam")
def ingest_roam(filepath: Path, graph_name: str, output_dir: Path) -> None:
    """Write and validate an authoritative package from a Roam JSON export."""
    try:
        package = build_package(RoamParser(), filepath, output_dir, source_scope=graph_name)
    except (OSError, ValueError, PackageValidationError) as exc:
        typer.echo(json.dumps({"error": str(exc)}), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(_summary(package))


@app.command("validate")
def validate(path: Path) -> None:
    """Validate schemas, references, inventory, hashes, and fidelity."""
    try:
        package = CanonicalPackage(path)
    except (OSError, ValueError, PackageValidationError) as exc:
        typer.echo(json.dumps({"error": str(exc)}), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(_summary(package))


@app.command("ingest-markdown")
def ingest_markdown(filepath: Path, repository: str, output_dir: Path, source_path: str | None = None) -> None:
    """Capture one repository Markdown document using the shared package contract."""
    try:
        package = build_package(
            MarkdownAdapter(), filepath, output_dir,
            source_scope=repository, native_id=source_path or filepath.name,
        )
    except (OSError, ValueError, PackageValidationError) as exc:
        typer.echo(json.dumps({"error": str(exc)}), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(_summary(package))


@app.command("generate-schemas")
def generate_schemas(check: bool = typer.Option(False, "--check")) -> None:
    """Generate schemas, or fail when committed contracts have drifted."""
    script = Path(__file__).resolve().parents[2] / "scripts" / "generate_schemas.py"
    completed = subprocess.run([sys.executable, str(script), *(["--check"] if check else [])], check=False)
    if completed.returncode:
        raise typer.Exit(code=completed.returncode)


@app.command("propose-methodology")
def propose_methodology_command(package_path: Path, proposals_path: Path, principal: str = "local-operator") -> None:
    """Draft evidence-grounded Roam methodology rules without activating them."""
    try:
        package = CanonicalPackage(package_path)
        proposals = propose_methodology(package, principal_id=principal)
        for proposal in proposals:
            validate_proposal(package, proposal)
        write_proposals(proposals_path, proposals)
    except Exception as exc:
        typer.echo(json.dumps({"error": str(exc)}), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps({"proposal_count": len(proposals), "path": str(proposals_path)}))


@app.command("propose-domain-claims")
def propose_domain_claims_command(package_path: Path, proposals_path: Path, principal: str = "local-operator") -> None:
    """Draft evidence-grounded ownership claims from repository Markdown."""
    try:
        package = CanonicalPackage(package_path)
        proposals = propose_domain_claims(package, principal_id=principal)
        for proposal in proposals:
            validate_proposal(package, proposal)
        write_proposals(proposals_path, proposals)
    except Exception as exc:
        typer.echo(json.dumps({"error": str(exc)}), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps({"proposal_count": len(proposals), "path": str(proposals_path)}))


@app.command("review")
def review_command(
    package_path: Path, proposals_path: Path, proposal_id: str,
    policy_path: Path, ledger_path: Path, reviewer_id: str, decision: str,
    rationale: str | None = None,
) -> None:
    """Record one authorized, immutable approval or rejection."""
    try:
        package = CanonicalPackage(package_path)
        proposal = next(item for item in read_proposals(proposals_path, package) if item.proposal_id == proposal_id)
        event = ReviewLedger(ledger_path).record(
            proposal, package, policy=load_review_policy(policy_path),
            reviewer_id=reviewer_id, decision=decision, rationale=rationale,
        )
    except Exception as exc:
        typer.echo(json.dumps({"error": str(exc)}), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(event.model_dump(mode="json"), sort_keys=True))


@app.command("publish-methodology")
def publish_methodology_command(package_path: Path, proposals_path: Path, ledger_path: Path, output: Path) -> None:
    """Publish only approved methodology rules."""
    try:
        package = CanonicalPackage(package_path)
        manifest = publish_methodology(
            package, read_proposals(proposals_path, package), ReviewLedger(ledger_path), output,
        )
    except Exception as exc:
        typer.echo(json.dumps({"error": str(exc)}), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps({"manifest_id": manifest.manifest_id, "approved_rules": len(manifest.rules)}))


@app.command("publish-domain-page")
def publish_domain_page_command(
    package_path: Path, proposals_path: Path, ledger_path: Path, output: Path,
    principal: str = "local-operator",
) -> None:
    """Render a reviewed Markdown page from approved domain claims."""
    try:
        package = CanonicalPackage(package_path)
        content = publish_reviewed_domain_page(
            package, read_proposals(proposals_path, package), ReviewLedger(ledger_path),
            output, principal_id=principal,
        )
    except Exception as exc:
        typer.echo(json.dumps({"error": str(exc)}), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps({"path": str(output), "bytes": len(content.encode("utf-8"))}))


@app.command("context")
def context_command(
    package_path: Path, query: str, task_type: str,
    principal: str = "local-operator",
    index_path: Annotated[Path | None, typer.Option("--index")] = None,
) -> None:
    """Assemble an access-aware lexical evidence bundle."""
    try:
        package = CanonicalPackage(package_path)
        bundle = (
            search_index(package, load_index(package, index_path), query, principal_id=principal, task_type=task_type)
            if index_path is not None else
            assemble_evidence_bundle(package, query, principal_id=principal, task_type=task_type)
        )
    except Exception as exc:
        typer.echo(json.dumps({"error": str(exc)}), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(bundle.model_dump(mode="json"), sort_keys=True))


@app.command("build-index")
def build_index_command(package_path: Path, output: Path) -> None:
    """Build a deterministic lexical and native-link projection."""
    try:
        index = write_index(CanonicalPackage(package_path), output)
    except Exception as exc:
        typer.echo(json.dumps({"error": str(exc)}), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps({
        "index_id": index.index_id, "terms": len(index.terms),
        "native_links": len(index.native_links),
    }, sort_keys=True))


@app.command("evaluate")
def evaluate_command(
    package_path: Path, index_path: Path, cases_path: Path,
    results_path: Path, proposals_path: Path,
) -> None:
    """Run labeled retrieval cases and propose reviewable fixes for misses."""
    try:
        package = CanonicalPackage(package_path)
        index = load_index(package, index_path)
        cases = read_evaluation_cases(cases_path)
        results = evaluate_retrieval(package, index, cases)
        proposals = propose_retrieval_changes(package, cases, results)
        for proposal in proposals:
            validate_proposal(package, proposal)
        write_evaluation_results(results_path, results)
        write_proposals(proposals_path, proposals)
    except Exception as exc:
        typer.echo(json.dumps({"error": str(exc)}), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps({
        "cases": len(cases), "passed": sum(item.passed for item in results),
        "retrieval_proposals": len(proposals),
    }, sort_keys=True))


@app.command("project-shared")
def project_shared_command(package_path: Path, output: Path) -> None:
    """Export the source-neutral content contract for another knowledge product."""
    try:
        snapshot = write_shared_content(CanonicalPackage(package_path), output)
    except Exception as exc:
        typer.echo(json.dumps({"error": str(exc)}), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps({
        "source_package_id": snapshot.source_package_id,
        "items": len(snapshot.items), "elements": len(snapshot.elements),
        "native_links": len(snapshot.native_links),
    }, sort_keys=True))


@app.command("project-markdown")
def project_markdown_command(package_path: Path, output_dir: Path) -> None:
    """Render an audit-oriented Markdown view with evidence and issue sidecars."""
    try:
        manifest = project_audit_markdown(CanonicalPackage(package_path), output_dir)
    except Exception as exc:
        typer.echo(json.dumps({"error": str(exc)}), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps({
        "projection_id": manifest.projection_id,
        "issue_count": manifest.issue_count,
        "path": str(output_dir),
    }, sort_keys=True))


@app.command("work-jobs")
def work_jobs(root: Path, max_jobs: int = 100) -> None:
    """Process queued ingestion jobs in a separate, restartable worker."""
    if max_jobs < 1:
        raise typer.BadParameter("max_jobs must be positive")
    store = JobStore(root)
    processed = 0
    failed = 0
    while processed < max_jobs:
        job = store.run_next()
        if job is None:
            break
        processed += 1
        failed += job.state == "failed"
    typer.echo(json.dumps({"processed": processed, "failed": failed}, sort_keys=True))


@app.command("serve-jobs")
def serve_jobs(root: Path, host: str = "127.0.0.1", port: int = 8775, max_upload_mb: int = 32) -> None:
    """Serve the local ingestion API; a separate work-jobs process handles jobs."""
    import uvicorn

    uvicorn.run(create_app(root, max_upload_bytes=max_upload_mb * 1024 * 1024), host=host, port=port)


if __name__ == "__main__":
    app()
