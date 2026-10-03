import json

from pkmcanon.evidence import assemble_evidence_bundle
from pkmcanon.models import AccessPolicy, SharedContentSnapshot
from pkmcanon.parsers.markdown import MarkdownAdapter
from pkmcanon.parsers.roam import RoamParser
from pkmcanon.shared import project_shared_content, write_shared_content
from pkmcanon.writer import build_package


def test_shared_projection_preserves_hierarchy_links_access_and_event_time(tmp_path):
    """Verify shared snapshots preserve source metadata and serialize deterministically."""
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
    assert elements["Parent"].source_locator.source_uid == "B"
    assert snapshot.contract_version == "0.2.0"
    assert all(row.item_id == item.item_id for row in snapshot.elements)
    assert {(row.kind, row.target_kind) for row in snapshot.native_links} == {("block_ref", "canonical"), ("tag", "tag")}
    output = tmp_path / "nested" / "shared.json"
    assert write_shared_content(package, output) == snapshot
    assert SharedContentSnapshot.model_validate_json(output.read_text()) == snapshot
    original = output.read_bytes()
    write_shared_content(package, output)
    assert output.read_bytes() == original
    assert not output.with_name(output.name + ".tmp").exists()


def test_shared_markdown_element_has_source_line_range(tmp_path):
    """Verify Markdown elements retain their source path and exact line range."""
    source = tmp_path / "character.md"
    source.write_text("# Cast\n\n## Kessa\n\n- Precise under pressure\n")
    package = build_package(
        MarkdownAdapter(), source, tmp_path / "package",
        source_scope="story", native_id="character.md",
    )
    snapshot = project_shared_content(package)
    element = next(row for row in snapshot.elements if row.text == "- Precise under pressure")
    assert element.source_locator.path == "character.md"
    assert element.source_locator.line_start == 5
    assert element.source_locator.line_end == 5


def test_portable_snapshot_and_evidence_bundle_resolve_same_immutable_source(tmp_path):
    """Verify snapshots and authorized evidence agree on source identity and location."""
    source = tmp_path / "character.md"
    source.write_text(
        "# Cast\n\n## Tavi Vale\n\n### Voice\n\n"
        "- Counts remaining turns under stress.\n\n## Neri\n\n- Speaks in metaphors.\n"
    )
    access = AccessPolicy(principal_ids=["creator"])
    first = build_package(MarkdownAdapter(), source, tmp_path / "first",
                          source_scope="canonworks-conformance", native_id="character.md", access=access)
    second = build_package(MarkdownAdapter(), source, tmp_path / "second",
                           source_scope="canonworks-conformance", native_id="character.md", access=access)
    assert first.manifest.package_id == second.manifest.package_id
    assert first.manifest.source_versions[0].source_version_id == second.manifest.source_versions[0].source_version_id
    snapshot = project_shared_content(first)
    bundle = assemble_evidence_bundle(first, "remaining turns", principal_id="creator", task_type="character-voice")
    assert bundle.source_package_id == snapshot.source_package_id
    assert len(bundle.evidence) == 1
    evidence = bundle.evidence[0]
    element = next(row for row in snapshot.elements if row.element_id == evidence.node_id)
    item = next(row for row in snapshot.items if row.item_id == element.item_id)
    source_version = next(row for row in snapshot.source_versions if row.source_version_id == item.source_version_id)
    assert evidence.source_version_id == source_version.source_version_id
    assert evidence.source_content_hash == source_version.content_hash
    assert evidence.quote == element.text[evidence.start:evidence.end]
    assert evidence.source_locator.line_start == element.source_locator.line_start == 7
    denied = assemble_evidence_bundle(first, "remaining turns", principal_id="stranger", task_type="character-voice")
    assert denied.evidence == []
