from pathlib import Path

import pytest

from pkmcanon.evidence import (
    assemble_evidence_bundle,
    evidence_for_node,
    validate_evidence,
)
from pkmcanon.index import build_index, search_index
from pkmcanon.models import AccessPolicy
from pkmcanon.package import PackageValidationError
from pkmcanon.parsers.markdown import MarkdownAdapter
from pkmcanon.writer import build_package


@pytest.fixture
def package(tmp_path):
    source = tmp_path / "page.md"
    source.write_text("# Service\n\nOwner: Café Team\n\nOwner: Other Team\n", encoding="utf-8")
    return build_package(MarkdownAdapter(), source, tmp_path / "package", source_scope="repo", native_id="docs/page.md")


def test_evidence_uses_character_offsets_and_source_line_locator(package):
    node = next(row for row in package.nodes if "Café" in row.plain_text)
    evidence = evidence_for_node(package, node.node_id, start=7, end=11)
    assert evidence.quote == "Café"
    assert (evidence.start, evidence.end) == (7, 11)
    assert (evidence.source_locator.char_start, evidence.source_locator.char_end) == (7, 11)
    assert evidence.source_locator.path == "docs/page.md"
    assert evidence.source_locator.line_start == evidence.source_locator.line_end == 3
    assert evidence.source_content_hash == package.manifest.source_versions[0].content_hash
    assert evidence.span_id == next(row.span_id for row in package.spans if row.node_id == node.node_id)
    validate_evidence(package, evidence)


@pytest.mark.parametrize("start,end", [(-1, 1), (2, 1), (0, 1000)])
def test_invalid_evidence_ranges_are_rejected(package, start, end):
    with pytest.raises(PackageValidationError, match="INVALID_EVIDENCE_RANGE"):
        evidence_for_node(package, package.nodes[0].node_id, start=start, end=end)


def test_evidence_allows_empty_range_at_end_but_rejects_unknown_node(package):
    node = package.nodes[0]
    evidence = evidence_for_node(package, node.node_id, start=len(node.plain_text))
    assert evidence.quote == ""
    assert evidence.start == evidence.end == len(node.plain_text)
    validate_evidence(package, evidence)
    with pytest.raises(PackageValidationError, match="DANGLING_EVIDENCE_NODE"):
        evidence_for_node(package, "absent")


@pytest.mark.parametrize("field,value", [
    ("quote", "forged"), ("source_content_hash", "0" * 64),
    ("source_version_id", "other-version"), ("evidence_id", "other-evidence"),
    ("span_id", "other-span"),
])
def test_evidence_rejects_tampered_provenance(package, field, value):
    evidence = evidence_for_node(package, package.nodes[0].node_id)
    with pytest.raises(PackageValidationError, match="EVIDENCE_MISMATCH"):
        validate_evidence(package, evidence.model_copy(update={field: value}))


@pytest.mark.parametrize("indexed", [False, True], ids=["lexical", "index"])
@pytest.mark.parametrize("query,limit,coverage,count", [
    ("OWNER team", 8, "complete", 2),
    ("owner absent", 8, "partial", 2),
    ("unmatched", 8, "none", 0),
    ("a an !!", 8, "none", 0),
    ("owner", 0, "none", 0),
    ("owner", -1, "none", 0),
    ("owner", 1, "complete", 1),
])
def test_retrieval_coverage_limits_and_deterministic_ties(package, indexed, query, limit, coverage, count):
    options = {"principal_id": "local-operator", "task_type": "lookup", "limit": limit}
    bundle = search_index(package, build_index(package), query, **options) if indexed else assemble_evidence_bundle(package, query, **options)
    assert bundle.coverage == coverage
    assert len(bundle.evidence) == count
    expected = sorted(row.node_id for row in package.nodes if "Owner:" in row.plain_text)
    assert [row.node_id for row in bundle.evidence] == expected[:count]


@pytest.mark.parametrize("visibility,principals,allowed", [
    ("public", [], True), ("private", [], False),
    ("restricted", ["reader"], True), ("restricted", ["someone-else"], False),
])
def test_both_retrieval_paths_enforce_source_access(tmp_path: Path, visibility, principals, allowed):
    source = tmp_path / "page.md"
    source.write_text("Owner: Team")
    package = build_package(MarkdownAdapter(), source, tmp_path / "package", source_scope="repo", access=AccessPolicy(visibility=visibility, principal_ids=principals))
    options = {"principal_id": "reader", "task_type": "ownership"}
    for bundle in (assemble_evidence_bundle(package, "owner", **options), search_index(package, build_index(package), "owner", **options)):
        assert bool(bundle.evidence) is allowed
        assert bundle.coverage == ("complete" if allowed else "none")
