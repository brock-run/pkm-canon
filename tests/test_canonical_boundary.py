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
    """Write a Roam fixture with linked blocks, an attribute, and an unsupported macro."""
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
    """Build a validated canonical package from the Roam fixture."""
    return build_package(RoamParser(), roam_source, tmp_path / "package", source_scope="test-graph")


def _update_inventory(root: Path, relative: str) -> None:
    """Refresh a mutated fixture file hash, byte length, and optional record count."""
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    content = (root / relative).read_bytes()
    manifest["files"][relative]["sha256"] = hashlib.sha256(content).hexdigest()
    manifest["files"][relative]["byte_length"] = len(content)
    if relative.endswith(".jsonl"):
        manifest["files"][relative]["record_count"] = sum(bool(line.strip()) for line in content.splitlines())
    manifest_path.write_text(json.dumps(manifest))


def _replace_record(root: Path, relative: str, update) -> None:
    """Apply a mutation to JSONL rows and refresh the fixture inventory."""
    path = root / relative
    rows = [json.loads(line) for line in path.read_text().splitlines() if line]
    update(rows)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    _update_inventory(root, relative)


def test_roam_package_is_complete_and_grounded(package: CanonicalPackage) -> None:
    """Verify normalized records, preserved source bytes, and diagnostics reconcile."""
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
    """Verify repeated ingestion yields identical records and reuses the same package."""
    one = build_package(RoamParser(), roam_source, tmp_path / "one", source_scope="test-graph")
    two = build_package(RoamParser(), roam_source, tmp_path / "two", source_scope="test-graph")
    for name in one.manifest.files:
        assert (one.root / name).read_bytes() == (two.root / name).read_bytes()
    assert one.manifest.package_id == two.manifest.package_id
    assert build_package(RoamParser(), roam_source, tmp_path / "one", source_scope="test-graph").manifest.package_id == one.manifest.package_id


def test_access_policy_changes_package_identity(tmp_path: Path, roam_source: Path) -> None:
    """Verify policy changes alter identity and cannot replace an existing package."""
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
    """Verify missing identity and time fields produce stable IDs and explicit diagnostics."""
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
    """Verify malformed block metadata is diagnosed and its raw payload is retained."""
    source = tmp_path / "invalid-fields.json"
    source.write_text('[{"uid":"P","title":"Page","children":[{"uid":"B","order":"first","create-time":"yesterday","string":"Text"}]}]')
    package = build_package(RoamParser(), source, tmp_path / "package", source_scope="test")
    assert package.manifest.fidelity.partial == 1
    assert {item.code for item in package.diagnostics} == {"INVALID_ORDER", "INVALID_CREATE_TIME"}
    assert package.preservation_records[0].storage.inline_utf8


@pytest.mark.parametrize("value", [True, False, float("inf"), 1e300])
def test_invalid_roam_timestamps_are_diagnosed_without_crashing(tmp_path: Path, value: object) -> None:
    source = tmp_path / "invalid-time.json"
    source.write_text(json.dumps([{"uid": "P", "title": "Page", "create-time": value}]))
    package = build_package(RoamParser(), source, tmp_path / "package", source_scope="test")
    assert package.documents[0].created_at is None
    assert any(item.code == "INVALID_CREATE_TIME" for item in package.diagnostics)


def test_bad_file_hash_fails(package: CanonicalPackage) -> None:
    """Verify appended bytes are rejected by the package inventory length check."""
    with (package.root / "nodes.jsonl").open("a") as stream:
        stream.write("{}\n")
    with pytest.raises(PackageValidationError, match="FILE_LENGTH_MISMATCH"):
        CanonicalPackage(package.root)


def test_changed_source_blob_fails_after_inventory_is_updated(package: CanonicalPackage) -> None:
    """Verify source storage checks detect tampering even with a refreshed inventory."""
    relative = "blobs/source-export.json"
    (package.root / relative).write_text("[]", encoding="utf-8")
    _update_inventory(package.root, relative)
    with pytest.raises(PackageValidationError, match="STORAGE_LENGTH_MISMATCH"):
        CanonicalPackage(package.root)


def test_fidelity_totals_must_reconcile(package: CanonicalPackage) -> None:
    """Verify inconsistent manifest fidelity totals are rejected."""
    manifest_path = package.root / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["fidelity"]["partial"] += 1
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(PackageValidationError, match="FIDELITY_MISMATCH"):
        CanonicalPackage(package.root)


def test_dangling_reference_fails_after_inventory_is_updated(package: CanonicalPackage) -> None:
    """Verify record reference checks reject an unknown document after inventory refresh."""
    _replace_record(package.root, "nodes.jsonl", lambda rows: rows[0].update(document_id="missing"))
    with pytest.raises(PackageValidationError, match="DANGLING_DOCUMENT"):
        CanonicalPackage(package.root)


def test_dangling_ancestor_fails_with_stable_error(tmp_path: Path) -> None:
    source = tmp_path / "nested.json"
    source.write_text('[{"uid":"P","title":"Page","children":[{"uid":"B1","string":"Parent","children":[{"uid":"B2","string":"Child"}]}]}]')
    package = build_package(RoamParser(), source, tmp_path / "package", source_scope="test")
    path = package.root / "nodes.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines() if line]
    parent = next(row for row in rows if row["plain_text"] == "Parent")
    child = next(row for row in rows if row["plain_text"] == "Child")
    parent["parent_node_id"] = "missing"
    path.write_text("".join(json.dumps(row) + "\n" for row in [child, parent]))
    _update_inventory(package.root, "nodes.jsonl")
    with pytest.raises(PackageValidationError, match="DANGLING_PARENT"):
        CanonicalPackage(package.root)


def test_duplicate_id_fails_after_inventory_is_updated(package: CanonicalPackage) -> None:
    """Verify duplicate node IDs are rejected even with a matching file inventory."""
    _replace_record(package.root, "nodes.jsonl", lambda rows: rows[1].update(node_id=rows[0]["node_id"]))
    with pytest.raises(PackageValidationError, match="DUPLICATE_ID"):
        CanonicalPackage(package.root)


def test_inventory_count_fails(package: CanonicalPackage) -> None:
    """Verify declared JSONL counts must match the actual record count."""
    manifest_path = package.root / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"]["nodes.jsonl"]["record_count"] += 1
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(PackageValidationError, match="RECORD_COUNT_MISMATCH"):
        CanonicalPackage(package.root)


def test_inventory_traversal_fails(package: CanonicalPackage) -> None:
    """Verify inventory paths cannot traverse outside the package directory."""
    manifest_path = package.root / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"]["../outside"] = manifest["files"]["nodes.jsonl"]
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(PackageValidationError, match="UNSAFE_PATH"):
        CanonicalPackage(package.root)


def test_strict_models_and_schemas_reject_unknown_fields() -> None:
    """Verify both runtime models and JSON Schemas reject undeclared document fields."""
    value = {"document_id": "a", "source_version_id": "b", "kind": "page", "title": "T", "surprise": True}
    with pytest.raises(ValidationError):
        Document.model_validate(value)
    with pytest.raises(SchemaValidationError):
        default_schema_store().validate_instance_with_short_name(value, "documents")


def test_storage_kind_matches_locator_in_model_and_schema() -> None:
    """Verify models and schemas reject a locator inconsistent with its storage kind."""
    value = {"storage_kind": "relative_path", "external_uri": "https://example.test"}
    with pytest.raises(ValidationError):
        SourceNativeReference.model_validate(value)
    with pytest.raises(SchemaValidationError):
        default_schema_store().validate_instance_with_short_name(value, "source-native-reference")


@pytest.mark.parametrize("relative,update,code", [
    ("documents.jsonl", {"source_version_id": "missing"}, "DANGLING_SOURCE_VERSION"),
    ("nodes.jsonl", {"parent_node_id": "missing"}, "DANGLING_PARENT"),
    ("spans.jsonl", {"node_id": "missing"}, "DANGLING_NODE"),
    ("spans.jsonl", {"end": 9999}, "INVALID_SPAN_RANGE"),
    ("spans.jsonl", {"text": "forged"}, "SPAN_TEXT_MISMATCH"),
    ("relations.jsonl", {"source_id": "missing"}, "DANGLING_RELATION_SOURCE"),
    ("attributes.jsonl", {"subject_id": "missing"}, "DANGLING_ATTRIBUTE_SUBJECT"),
    ("preservation_records.jsonl", {"subject_id": "missing"}, "DANGLING_PRESERVATION_SUBJECT"),
    ("diagnostics.jsonl", {"subject_id": "missing"}, "DANGLING_DIAGNOSTIC_SUBJECT"),
    ("diagnostics.jsonl", {"preservation_id": "missing"}, "DANGLING_DIAGNOSTIC_PRESERVATION"),
    ("diagnostics.jsonl", {"preservation_id": None}, "UNPRESERVED_OUTCOME"),
])
def test_semantic_corruption_fails_even_with_valid_inventory(package, relative, update, code):
    _replace_record(package.root, relative, lambda rows: rows[0].update(update))
    with pytest.raises(PackageValidationError, match=code):
        CanonicalPackage(package.root)


def test_parent_cannot_point_to_itself(package):
    _replace_record(package.root, "nodes.jsonl", lambda rows: rows[0].update(parent_node_id=rows[0]["node_id"]))
    with pytest.raises(PackageValidationError, match="PARENT_CYCLE"):
        CanonicalPackage(package.root)


def test_parent_cannot_belong_to_another_document(package):
    _replace_record(package.root, "nodes.jsonl", lambda rows: rows[0].update(parent_node_id=rows[1]["node_id"]))
    with pytest.raises(PackageValidationError, match="CROSS_DOCUMENT_PARENT"):
        CanonicalPackage(package.root)


@pytest.mark.parametrize("target_kind,valid", [("canonical", False), ("external", True)])
def test_only_canonical_relation_targets_must_exist(package, target_kind, valid):
    _replace_record(package.root, "relations.jsonl", lambda rows: rows[0].update(target_id="https://example.test", target_kind=target_kind))
    if valid:
        assert CanonicalPackage(package.root).relations[0].target_kind == "external"
    else:
        with pytest.raises(PackageValidationError, match="DANGLING_RELATION_TARGET"):
            CanonicalPackage(package.root)


@pytest.mark.parametrize("line", ["{bad json}", "[]", "null"])
def test_invalid_jsonl_reports_filename_and_line(package, line):
    (package.root / "nodes.jsonl").write_text("\n" + line + "\n")
    _update_inventory(package.root, "nodes.jsonl")
    with pytest.raises(PackageValidationError, match=r"INVALID_JSONL: nodes.jsonl:2"):
        CanonicalPackage(package.root)


def test_same_length_tampering_is_detected_by_hash(package):
    path = package.root / "nodes.jsonl"
    original = path.read_bytes()
    changed = original.replace(b"Evidence", b"Tampered")
    assert changed != original and len(changed) == len(original)
    path.write_bytes(changed)
    with pytest.raises(PackageValidationError, match="FILE_HASH_MISMATCH"):
        CanonicalPackage(package.root)


def test_uninventoried_files_are_rejected(package):
    (package.root / "untracked.txt").write_text("unexpected")
    with pytest.raises(PackageValidationError, match="INVENTORY_MISMATCH"):
        CanonicalPackage(package.root)


def test_inventory_symlink_is_rejected_even_when_bytes_match(package, tmp_path):
    path = package.root / "nodes.jsonl"
    outside = tmp_path / "outside.jsonl"
    path.rename(outside)
    path.symlink_to(outside)
    with pytest.raises(PackageValidationError, match="UNSAFE_PATH"):
        CanonicalPackage(package.root)
def test_missing_schema_root_has_actionable_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Generate or restore docs/specs/schemas"):
        default_schema_store(tmp_path / "missing")


@pytest.mark.parametrize("relative", ["/absolute", "./nodes.jsonl", "blobs//source-export.json", "blobs\\source-export.json"])
def test_inventory_rejects_noncanonical_paths(package, relative):
    path = package.root / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["files"][relative] = manifest["files"]["nodes.jsonl"]
    path.write_text(json.dumps(manifest))
    with pytest.raises(PackageValidationError, match="UNSAFE_PATH"):
        CanonicalPackage(package.root)


def test_inventory_rejects_directory_symlink_escape(package, tmp_path):
    directory = package.root / "blobs"
    outside = tmp_path / "outside-blobs"
    directory.rename(outside)
    directory.symlink_to(outside, target_is_directory=True)
    with pytest.raises(PackageValidationError, match="UNSAFE_PATH"):
        CanonicalPackage(package.root)


@pytest.mark.parametrize("mutation,code", [
    ("missing-family", "INVENTORY_MISSING_FAMILY"),
    ("blob-record-count", "INVENTORY_MISMATCH"),
    ("duplicate-source", "DUPLICATE_SOURCE_VERSION"),
    ("source-hash", "SOURCE_HASH_MISMATCH"),
])
def test_manifest_integrity_constraints(package, mutation, code):
    path = package.root / "manifest.json"
    manifest = json.loads(path.read_text())
    if mutation == "missing-family":
        del manifest["files"]["nodes.jsonl"]
    elif mutation == "blob-record-count":
        manifest["files"]["blobs/source-export.json"]["record_count"] = 1
    elif mutation == "duplicate-source":
        manifest["source_versions"].append(manifest["source_versions"][0].copy())
    else:
        manifest["source_versions"][0]["content_hash"] = "0" * 64
    path.write_text(json.dumps(manifest))
    with pytest.raises(PackageValidationError, match=code):
        CanonicalPackage(package.root)
