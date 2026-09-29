import json
from pathlib import Path

import pytest

from pkmcanon.package import PackageValidationError
from pkmcanon.parsers.roam import RoamParser
from pkmcanon.projection import project_audit_markdown, validate_projection
from pkmcanon.writer import build_package


def test_audit_projection_is_rebuildable_and_links_back_to_source(tmp_path: Path) -> None:
    """Verify projection reuse, evidence mappings, and detection of manifest and page tampering."""
    source = tmp_path / "roam.json"
    source.write_text(json.dumps([
        {"uid": "P", "title": "Projects", "children": [
            {"uid": "B1", "order": 0, "string": "Parent {{query: test}}", "children": [
                {"uid": "B2", "order": 0, "string": "Child"},
            ]},
        ]},
    ]))
    package = build_package(RoamParser(), source, tmp_path / "package", source_scope="personal")
    output = tmp_path / "audit"
    manifest = project_audit_markdown(package, output)
    assert manifest.issue_count == 1
    assert validate_projection(output) == manifest
    assert project_audit_markdown(package, output) == manifest
    page = next(output.glob("*.md")).read_text()
    assert "# Projects" in page and "Parent" in page and "  - Child" in page
    evidence = [json.loads(line) for line in (output / "evidence-map.jsonl").read_text().splitlines()]
    assert len(evidence) == 2
    assert all(row["source_content_hash"] == package.manifest.source_versions[0].content_hash for row in evidence)
    issues = [json.loads(line) for line in (output / "projection-issues.jsonl").read_text().splitlines()]
    assert issues[0]["code"] == "UNSUPPORTED_MACRO"
    manifest_path = output / "projection-manifest.json"
    saved_manifest = manifest_path.read_text()
    tampered = json.loads(saved_manifest)
    tampered["issue_count"] += 1
    manifest_path.write_text(json.dumps(tampered))
    with pytest.raises(PackageValidationError, match="PROJECTION_ISSUE_COUNT_MISMATCH"):
        validate_projection(output)
    manifest_path.write_text(saved_manifest)
    with next(output.glob("*.md")).open("a") as stream:
        stream.write("changed")
    with pytest.raises(PackageValidationError, match="PROJECTION_HASH_MISMATCH"):
        validate_projection(output)
