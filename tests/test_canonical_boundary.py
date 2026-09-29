import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError as SchemaValidationError
from pydantic import ValidationError

from pkmcanon.models import AccessPolicy, Document, SourceNativeReference
from pkmcanon.package import CanonicalPackage, PackageValidationError
from pkmcanon.parsers.roam import RoamParser
from pkmcanon.schema_validation import default_schema_store
from pkmcanon.writer import build_package


@pytest.fixture
def roam_source(tmp_path: Path) -> Path:
    source = [
        {
            "uid": "P1", "title": "Project",
            "children": [{"uid": "B1", "order": 0, "string": "Status:: todo [[Other]] ((B2)) #work {{query: test}}"}],
        },
        {"uid": "P2", "title": "Other", "children": [{"uid": "B2", "string": "Evidence"}]},
    ]
    path = tmp_path / "roam.json"
    path.write_text(json.dumps(source), encoding="utf-8")
    return path


@pytest.fixture
def package(tmp_path: Path, roam_source: Path) -> CanonicalPackage:
    return build_package(RoamParser(), roam_source, tmp_path / "package", source_scope="test-graph")


def _update_inventory(root: Path, relative: str) -> None:
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    content = (root / relative).read_bytes()
    manifest["files"][relative]["sha256"] = hashlib.sha256(content).hexdigest()
    manifest["files"][relative]["byte_length"] = len(content)
    if relative.endswith(".jsonl"):
        manifest["files"][relative]["record_count"] = sum(bool(line.strip()) for line in content.splitlines())
    manifest_path.write_text(json.dumps(manifest))


def _replace_record(root: Path, relative: str, update) -> None:
    path = root / relative
    rows = [json.loads(line) for line in path.read_text().splitlines() if line]
    update(rows)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    _update_inventory(root, relative)


def test_roam_package_is_complete_and_grounded(package: CanonicalPackage) -> None:
    assert package.manifest.fidelity.source_object_count == 4
    assert package.manifest.fidelity.partial == 1
    assert package.manifest.fidelity.normalized == 3
    assert {item.relation_type for item in package.relations} == {"page_ref", "block_ref", "tag"}
    assert len(package.attributes) == 1
    assert len(package.spans) == len(package.nodes)
    assert any(item.code == "UNSUPPORTED_MACRO" for item in package.diagnostics)
    assert package.diagnostics[0].preservation_id == package.preservation_records[0].id
    assert (package.root / "blobs/source-export.json").read_bytes()


def test_replay_has_stable_records_and_is_idempotent(tmp_path: Path, roam_source: Path) -> None:
    one = build_package(RoamParser(), roam_source, tmp_path / "one", source_scope="test-graph")
    two = build_package(RoamParser(), roam_source, tmp_path / "two", source_scope="test-graph")
    for name in one.manifest.files:
        assert (one.root / name).read_bytes() == (two.root / name).read_bytes()
    assert one.manifest.package_id == two.manifest.package_id
    assert build_package(RoamParser(), roam_source, tmp_path / "one", source_scope="test-graph").manifest.package_id == one.manifest.package_id


def test_access_policy_changes_package_identity(tmp_path: Path, roam_source: Path) -> None:
    private = build_package(RoamParser(), roam_source, tmp_path / "private", source_scope="test-graph")
    wider = build_package(
        RoamParser(), roam_source, tmp_path / "wider", source_scope="test-graph",
        access=AccessPolicy(visibility="restricted", principal_ids=["local-operator", "teammate"]),
    )
    assert private.manifest.package_id != wider.manifest.package_id
    with pytest.raises(PackageValidationError, match="PACKAGE_EXISTS"):
        build_package(
            RoamParser(), roam_source, tmp_path / "private", source_scope="test-graph",
            access=AccessPolicy(visibility="restricted", principal_ids=["local-operator", "teammate"]),
        )


def test_missing_uid_and_timestamp_do_not_use_random_or_wall_clock(tmp_path: Path) -> None:
    source = tmp_path / "missing.json"
    source.write_text('[{"title":"Untimed","children":[{"string":"Block"}]}]')
    first = build_package(RoamParser(), source, tmp_path / "first", source_scope="test")
    second = build_package(RoamParser(), source, tmp_path / "second", source_scope="test")
    assert first.documents[0].created_at is None
    assert first.documents[0].document_id == second.documents[0].document_id
    assert first.nodes[0].node_id == second.nodes[0].node_id
    assert first.manifest.fidelity.partial == 2
    assert {item.code for item in first.diagnostics} == {"MISSING_UID"}


def test_invalid_block_order_and_time_are_diagnosed_and_preserved(tmp_path: Path) -> None:
    source = tmp_path / "invalid-fields.json"
    source.write_text('[{"uid":"P","title":"Page","children":[{"uid":"B","order":"first","create-time":"yesterday","string":"Text"}]}]')
    package = build_package(RoamParser(), source, tmp_path / "package", source_scope="test")
    assert package.manifest.fidelity.partial == 1
    assert {item.code for item in package.diagnostics} == {"INVALID_ORDER", "INVALID_CREATE_TIME"}
    assert package.preservation_records[0].storage.inline_utf8


def test_bad_file_hash_fails(package: CanonicalPackage) -> None:
    with (package.root / "nodes.jsonl").open("a") as stream:
        stream.write("{}\n")
    with pytest.raises(PackageValidationError, match="FILE_LENGTH_MISMATCH"):
        CanonicalPackage(package.root)


def test_changed_source_blob_fails_after_inventory_is_updated(package: CanonicalPackage) -> None:
    relative = "blobs/source-export.json"
    (package.root / relative).write_text("[]", encoding="utf-8")
    _update_inventory(package.root, relative)
    with pytest.raises(PackageValidationError, match="STORAGE_LENGTH_MISMATCH"):
        CanonicalPackage(package.root)


def test_fidelity_totals_must_reconcile(package: CanonicalPackage) -> None:
    manifest_path = package.root / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["fidelity"]["partial"] += 1
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(PackageValidationError, match="FIDELITY_MISMATCH"):
        CanonicalPackage(package.root)


def test_dangling_reference_fails_after_inventory_is_updated(package: CanonicalPackage) -> None:
    _replace_record(package.root, "nodes.jsonl", lambda rows: rows[0].update(document_id="missing"))
    with pytest.raises(PackageValidationError, match="DANGLING_DOCUMENT"):
        CanonicalPackage(package.root)


def test_duplicate_id_fails_after_inventory_is_updated(package: CanonicalPackage) -> None:
    _replace_record(package.root, "nodes.jsonl", lambda rows: rows[1].update(node_id=rows[0]["node_id"]))
    with pytest.raises(PackageValidationError, match="DUPLICATE_ID"):
        CanonicalPackage(package.root)


def test_inventory_count_fails(package: CanonicalPackage) -> None:
    manifest_path = package.root / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"]["nodes.jsonl"]["record_count"] += 1
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(PackageValidationError, match="RECORD_COUNT_MISMATCH"):
        CanonicalPackage(package.root)


def test_inventory_traversal_fails(package: CanonicalPackage) -> None:
    manifest_path = package.root / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"]["../outside"] = manifest["files"]["nodes.jsonl"]
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(PackageValidationError, match="UNSAFE_PATH"):
        CanonicalPackage(package.root)


def test_strict_models_and_schemas_reject_unknown_fields() -> None:
    value = {"document_id": "a", "source_version_id": "b", "kind": "page", "title": "T", "surprise": True}
    with pytest.raises(ValidationError):
        Document.model_validate(value)
    with pytest.raises(SchemaValidationError):
        default_schema_store().validate_instance_with_short_name(value, "documents")


def test_storage_kind_matches_locator_in_model_and_schema() -> None:
    value = {"storage_kind": "relative_path", "external_uri": "https://example.test"}
    with pytest.raises(ValidationError):
        SourceNativeReference.model_validate(value)
    with pytest.raises(SchemaValidationError):
        default_schema_store().validate_instance_with_short_name(value, "source-native-reference")
