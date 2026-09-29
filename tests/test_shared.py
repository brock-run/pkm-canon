import json

from pkmcanon.models import SharedContentSnapshot
from pkmcanon.parsers.roam import RoamParser
from pkmcanon.shared import project_shared_content, write_shared_content
from pkmcanon.writer import build_package


def test_shared_projection_preserves_hierarchy_links_access_and_event_time(tmp_path):
    source = tmp_path / "roam.json"
    source.write_text(json.dumps([{
        "uid": "P", "title": "Page", "create-time": 0, "edit-time": 1000,
        "children": [{"uid": "B", "string": "Parent", "children": [
            {"uid": "C", "string": "((B)) #work"},
        ]}],
    }]))
    package = build_package(RoamParser(), source, tmp_path / "package", source_scope="graph")
    snapshot = project_shared_content(package)
    assert snapshot.source_versions == package.manifest.source_versions
    item = snapshot.items[0]
    assert item.source_event_time == "1970-01-01T00:00:01+00:00"
    assert item.observed_at == package.manifest.source_versions[0].observed_at
    assert item.access == package.manifest.source_versions[0].access
    elements = {row.text: row for row in snapshot.elements}
    assert elements["((B)) #work"].parent_element_id == elements["Parent"].element_id
    assert all(row.item_id == item.item_id for row in snapshot.elements)
    assert {(row.kind, row.target_kind) for row in snapshot.native_links} == {("block_ref", "canonical"), ("tag", "tag")}
    output = tmp_path / "nested" / "shared.json"
    assert write_shared_content(package, output) == snapshot
    assert SharedContentSnapshot.model_validate_json(output.read_text()) == snapshot
    original = output.read_bytes()
    write_shared_content(package, output)
    assert output.read_bytes() == original
    assert not output.with_name(output.name + ".tmp").exists()
