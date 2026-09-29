import json
from pathlib import Path

import pytest

from pkmcanon.index import (
    build_index,
    load_index,
    related_content_ids,
    search_index,
    write_index,
)
from pkmcanon.package import PackageValidationError
from pkmcanon.parsers.roam import RoamParser
from pkmcanon.writer import build_package


def test_index_rebuilds_and_filters_before_serving(tmp_path: Path) -> None:
    """Verify deterministic indexes, access filtering, result limits, and tampering detection."""
    source = tmp_path / "roam.json"
    source.write_text(json.dumps([
        {"uid": "P1", "title": "Project", "children": [{"uid": "B1", "string": "See [[Other]] for platform ownership"}]},
        {"uid": "P2", "title": "Other", "children": [{"uid": "B2", "string": "Platform Team owns this service"}]},
    ]))
    package = build_package(RoamParser(), source, tmp_path / "package", source_scope="personal")
    path = tmp_path / "index.json"
    index = write_index(package, path)
    assert index == build_index(package)
    assert index == load_index(package, path)
    allowed = search_index(package, index, "platform ownership", principal_id="local-operator", task_type="lookup")
    denied = search_index(package, index, "platform ownership", principal_id="stranger", task_type="lookup")
    assert len(allowed.evidence) == 2
    assert denied.evidence == []
    assert search_index(package, index, "platform", principal_id="local-operator", task_type="lookup", limit=0).evidence == []
    source_node = next(node for node in package.nodes if "See" in node.plain_text)
    target_doc = next(doc for doc in package.documents if doc.title == "Other")
    assert related_content_ids(package, index, source_node.node_id, principal_id="local-operator") == [target_doc.document_id]
    assert related_content_ids(package, index, source_node.node_id, principal_id="stranger") == []
    raw = json.loads(path.read_text())
    raw["terms"]["platform"] = []
    path.write_text(json.dumps(raw))
    with pytest.raises(PackageValidationError, match="INDEX_STALE_OR_TAMPERED"):
        load_index(package, path)


@pytest.fixture
def linked_package(tmp_path):
    source = tmp_path / "links.json"
    source.write_text(json.dumps([
        {"uid": "P", "title": "Page", "children": [
            {"uid": "B", "string": "PLATFORM platform ownership [[Target]] [[Target]] ((T)) #work"},
            {"uid": "C", "string": "platform"},
        ]},
        {"uid": "Q", "title": "Target", "children": [{"uid": "T", "string": "Target text"}]},
    ]))
    return build_package(RoamParser(), source, tmp_path / "package", source_scope="graph")


def test_index_deduplicates_terms_and_ranks_distinct_query_matches(linked_package):
    package = linked_package
    index = build_index(package)
    best = next(row for row in package.nodes if "ownership" in row.plain_text)
    other = next(row for row in package.nodes if row.plain_text == "platform")
    assert index.terms["platform"] == sorted([best.node_id, other.node_id])
    assert "PLATFORM" not in index.terms
    bundle = search_index(package, index, "platform PLATFORM ownership", principal_id="local-operator", task_type="lookup", limit=1)
    assert [row.node_id for row in bundle.evidence] == [best.node_id]
    assert bundle.coverage == "complete"
    assert search_index(package, index, "plat", principal_id="local-operator", task_type="lookup").evidence == []


def test_related_content_deduplicates_canonical_targets_and_excludes_tags(linked_package):
    package = linked_package
    index = build_index(package)
    source = next(row for row in package.nodes if "ownership" in row.plain_text)
    document = next(row for row in package.documents if row.title == "Target")
    node = next(row for row in package.nodes if row.plain_text == "Target text")
    assert related_content_ids(package, index, source.node_id, principal_id="local-operator") == sorted([document.document_id, node.node_id])
    assert related_content_ids(package, index, "missing", principal_id="local-operator") == []
    assert related_content_ids(package, index, node.node_id, principal_id="local-operator") == []


@pytest.mark.parametrize("operation", ["search", "related"])
def test_index_consumers_reject_another_packages_index(linked_package, operation):
    index = build_index(linked_package).model_copy(update={"source_package_id": "other-package"})
    with pytest.raises(PackageValidationError, match="INDEX_PACKAGE_MISMATCH"):
        if operation == "search":
            search_index(linked_package, index, "platform", principal_id="local-operator", task_type="lookup")
        else:
            related_content_ids(linked_package, index, linked_package.nodes[0].node_id, principal_id="local-operator")


@pytest.mark.parametrize("field,value", [
    ("index_id", "forged"), ("source_package_id", "foreign"),
    ("profile_version", "unknown"), ("native_links", []),
])
def test_loading_index_rejects_provenance_and_link_tampering(linked_package, tmp_path, field, value):
    path = tmp_path / "index.json"
    write_index(linked_package, path)
    raw = json.loads(path.read_text())
    raw[field] = value
    path.write_text(json.dumps(raw))
    with pytest.raises(PackageValidationError, match="INDEX_STALE_OR_TAMPERED"):
        load_index(linked_package, path)
