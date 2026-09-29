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
