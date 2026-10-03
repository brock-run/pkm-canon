import json

import pytest
from typer.testing import CliRunner

from pkmcanon.cli import app
from pkmcanon.package import CanonicalPackage


@pytest.mark.parametrize("command,data,scope", [
    ("ingest-markdown", b"# Service\n\nOwner: Team\n", "repo"),
    ("ingest-roam", b'[{"uid":"P","title":"Page"}]', "graph"),
])
def test_ingest_and_validate_commands_report_same_package(tmp_path, command, data, scope):
    source = tmp_path / "source.txt"
    source.write_bytes(data)
    output = tmp_path / "package"
    runner = CliRunner()
    result = runner.invoke(app, [command, str(source), scope, str(output)])
    assert result.exit_code == 0, result.output
    summary = json.loads(result.stdout)
    assert summary["package_id"] == CanonicalPackage(output).manifest.package_id
    assert summary["record_counts"]["documents.jsonl"] == 1
    checked = runner.invoke(app, ["validate", str(output)])
    assert checked.exit_code == 0, checked.output
    assert json.loads(checked.stdout) == summary


def test_ingest_roam_named_principal_controls_private_review_source(tmp_path):
    source = tmp_path / "source.json"
    source.write_text('[{"uid":"P","title":"Page","children":[{"uid":"B","string":"Type:: note"}]}]')
    package_path = tmp_path / "package"
    proposals_path = tmp_path / "proposals.jsonl"
    runner = CliRunner()
    ingest = runner.invoke(app, ["ingest-roam", str(source), "my-graph", str(package_path), "--principal", "brock-butler"])
    assert ingest.exit_code == 0, ingest.output
    package = CanonicalPackage(package_path)
    assert package.manifest.source_versions[0].access.principal_ids == ["brock-butler"]
    proposed = runner.invoke(app, ["propose-methodology", str(package_path), str(proposals_path), "--principal", "brock-butler"])
    assert proposed.exit_code == 0, proposed.output
    assert json.loads(proposed.stdout)["proposal_count"] == 1
    denied = runner.invoke(app, ["propose-methodology", str(package_path), str(tmp_path / "denied.jsonl")])
    assert denied.exit_code == 0, denied.output
    assert json.loads(denied.stdout)["proposal_count"] == 0


@pytest.mark.parametrize("command,data,code", [
    ("ingest-roam", b"{}", "INVALID_ROAM_ROOT"),
    ("ingest-markdown", b"\xff", "INVALID_MARKDOWN_ENCODING"),
])
def test_invalid_ingestion_reports_json_error_and_no_package(tmp_path, command, data, code):
    source = tmp_path / "source"
    source.write_bytes(data)
    output = tmp_path / "package"
    result = CliRunner().invoke(app, [command, str(source), "scope", str(output)])
    assert result.exit_code == 1
    assert code in json.loads(result.stderr)["error"]
    assert result.stdout == ""
    assert not output.exists()


def test_audit_fidelity_ranks_diagnostics_without_exposing_source_text(tmp_path):
    source = tmp_path / "source.json"
    source.write_text(json.dumps([{"uid": "P", "title": "Private page", "children": [
        {"uid": "B", "string": "Secret [[missing]]", "heading": 1},
    ]}]))
    package = tmp_path / "package"
    runner = CliRunner()
    assert runner.invoke(app, ["ingest-roam", str(source), "graph", str(package)]).exit_code == 0
    result = runner.invoke(app, ["audit-fidelity", str(package), "--top", "1"])
    assert result.exit_code == 0, result.output
    audit = json.loads(result.stdout)
    assert audit["fidelity"]["warning_count"] == 2
    assert audit["distinct_diagnostic_codes"] == 2
    assert audit["diagnostics"] == [{
        "code": "UNRESOLVED_PAGE_REF", "severity": "warning",
        "outcome": "unresolved_reference", "count": 1,
    }]
    assert "Secret" not in result.stdout
    assert "Private page" not in result.stdout
    invalid = runner.invoke(app, ["audit-fidelity", str(package), "--top", "0"])
    assert invalid.exit_code == 2


def test_methodology_review_packet_is_local_escaped_and_read_only(tmp_path):
    source = tmp_path / "source.json"
    source.write_text(json.dumps([{"uid": "P", "title": "Page", "children": [
        {"uid": "B", "string": "Unsafe<script>:: <img src=x>"},
    ]}]))
    package = tmp_path / "package"
    proposals = tmp_path / "proposals.jsonl"
    packet = tmp_path / "review.html"
    runner = CliRunner()
    assert runner.invoke(app, ["ingest-roam", str(source), "graph", str(package)]).exit_code == 0
    assert runner.invoke(app, ["propose-methodology", str(package), str(proposals)]).exit_code == 0
    rendered = runner.invoke(app, ["render-methodology-review", str(package), str(proposals), str(packet)])
    assert rendered.exit_code == 0, rendered.output
    assert json.loads(rendered.stdout)["proposal_count"] == 1
    html = packet.read_text()
    assert "Unsafe&lt;script&gt;::" in html
    assert "&lt;img src=x&gt;" in html
    assert "<script>" not in html
    assert "Decision: unreviewed" in html
    assert not (tmp_path / "reviews").exists()
    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps({"policy_version": "test-v1", "approved_reviewers": ["local-operator"]}))
    proposal_id = json.loads(proposals.read_text().splitlines()[0])["proposal_id"]
    reviewed = runner.invoke(app, [
        "review", str(package), str(proposals), proposal_id,
        str(policy), str(tmp_path / "reviews"), "local-operator", "approved",
    ])
    assert reviewed.exit_code == 0, reviewed.output
    rerendered = runner.invoke(app, [
        "render-methodology-review", str(package), str(proposals), str(packet),
        "--ledger", str(tmp_path / "reviews"), "--policy", str(policy),
    ])
    assert rerendered.exit_code == 0, rerendered.output
    assert "Decision: approved" in packet.read_text()


def test_context_command_index_option_and_principal_filter(tmp_path):
    source = tmp_path / "page.md"
    source.write_text("Owner: Team")
    package = tmp_path / "package"
    index = tmp_path / "index.json"
    runner = CliRunner()
    assert runner.invoke(app, ["ingest-markdown", str(source), "repo", str(package), "--source-path", "docs/page.md"]).exit_code == 0
    assert runner.invoke(app, ["build-index", str(package), str(index)]).exit_code == 0
    for options in ([], ["--index", str(index)]):
        result = runner.invoke(app, ["context", str(package), "owner", "ownership", *options])
        assert result.exit_code == 0, result.output
        bundle = json.loads(result.stdout)
        assert bundle["coverage"] == "complete"
        assert bundle["evidence"][0]["source_locator"]["path"] == "docs/page.md"
        denied = runner.invoke(app, ["context", str(package), "owner", "ownership", "--principal", "stranger", *options])
        assert denied.exit_code == 0, denied.output
        assert json.loads(denied.stdout)["evidence"] == []


@pytest.mark.parametrize("limit", ["0", "-1"])
def test_worker_cli_rejects_nonpositive_job_limit(tmp_path, limit):
    result = CliRunner().invoke(app, ["work-jobs", str(tmp_path / "jobs"), "--max-jobs", limit])
    assert result.exit_code == 2
    assert "max_jobs must be positive" in result.output
    assert not (tmp_path / "jobs").exists()
