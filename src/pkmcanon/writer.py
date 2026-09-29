"""Atomic package writer for versioned source adapters."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from .adapters import SourceAdapter, stable_id
from .models import (
    AccessPolicy,
    Attribute,
    Diagnostic,
    Document,
    FidelitySummary,
    FileInventoryEntry,
    Manifest,
    Node,
    ParserDescriptor,
    PreservationBundle,
    PreservationRecord,
    Relation,
    SourceNativeReference,
    SourceProfile,
    SourceVersion,
    Span,
)
from .package import RECORD_FAMILIES, CanonicalPackage, PackageValidationError
from .storage import CanonicalStore, FilesystemPackageStore

MODEL_FILES: dict[type[BaseModel], str] = {
    Document: "documents.jsonl",
    Node: "nodes.jsonl",
    Span: "spans.jsonl",
    Relation: "relations.jsonl",
    Attribute: "attributes.jsonl",
    PreservationRecord: "preservation_records.jsonl",
    PreservationBundle: "preservation_bundles.jsonl",
    Diagnostic: "diagnostics.jsonl",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _serialize(model: BaseModel) -> str:
    return json.dumps(model.model_dump(mode="json", by_alias=True, exclude_none=True), sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def build_package(
    adapter: SourceAdapter,
    source_path: Path,
    output_dir: Path,
    *,
    source_scope: str,
    native_id: str | None = None,
    access: AccessPolicy | None = None,
    store: CanonicalStore | None = None,
) -> CanonicalPackage:
    """Parse a source snapshot, validate a staged package, then publish it."""
    source_path = Path(source_path)
    output_dir = Path(output_dir)
    store = store or FilesystemPackageStore()
    data = source_path.read_bytes()
    source_hash = _sha256(data)
    native_id = native_id or source_path.name
    access = access or AccessPolicy(principal_ids=["local-operator"])
    source_version_id = stable_id("srcver", adapter.source_system, source_scope, native_id, source_hash)
    package_id = stable_id(
        "pkg", source_version_id, adapter.name, adapter.version,
        adapter.profile_version, adapter.contract_version,
        json.dumps(access.model_dump(mode="json"), sort_keys=True, separators=(",", ":")),
    )
    if output_dir.exists():
        existing = store.open(output_dir)
        if existing.manifest.package_id == package_id:
            return existing
        raise PackageValidationError("PACKAGE_EXISTS", str(output_dir))
    result = adapter.parse(data, source_scope=source_scope, source_version_id=source_version_id, native_id=native_id)
    rows: dict[str, list[BaseModel]] = {name: [] for name in RECORD_FAMILIES}
    for record in result.records + result.diagnostics:
        filename = MODEL_FILES.get(type(record))
        if filename is None:
            raise PackageValidationError("UNKNOWN_RECORD_TYPE", type(record).__name__)
        rows[filename].append(record)
    partial_subjects = {item.subject_id for item in result.diagnostics if item.outcome == "partial"}
    represented = len(rows["documents.jsonl"]) + len(rows["nodes.jsonl"])
    fidelity = FidelitySummary(
        source_object_count=result.source_object_count,
        normalized=represented - len(partial_subjects),
        partial=len(partial_subjects),
        preserved_only=sum(item.outcome == "preserved_only" for item in result.diagnostics),
        unsupported=sum(item.outcome == "unsupported" for item in result.diagnostics),
        rejected=sum(item.outcome == "rejected" for item in result.diagnostics),
        unresolved_reference_count=sum(item.outcome == "unresolved_reference" for item in result.diagnostics),
        warning_count=sum(item.severity == "warning" for item in result.diagnostics),
        error_count=sum(item.severity == "error" for item in result.diagnostics),
    )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=output_dir.parent))
    try:
        suffix = source_path.suffix.lower() if source_path.suffix.lower() in {".json", ".md", ".txt"} else ".bin"
        source_relative = f"blobs/source-export{suffix}"
        (stage / "blobs").mkdir()
        (stage / source_relative).write_bytes(data)
        for filename, records in rows.items():
            descriptor = RECORD_FAMILIES[filename]
            records.sort(key=lambda item: getattr(item, descriptor[2]))
            content = "".join(_serialize(item) + "\n" for item in records)
            (stage / filename).write_text(content, encoding="utf-8")
        files: dict[str, FileInventoryEntry] = {}
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                relative = path.relative_to(stage).as_posix()
                content = path.read_bytes()
                files[relative] = FileInventoryEntry(
                    sha256=_sha256(content), byte_length=len(content),
                    record_count=len(rows[relative]) if relative in rows else None,
                )
        created_at = datetime.now(UTC).isoformat()
        manifest = Manifest(
            package_id=package_id, package_schema_version="0.1.0",
            created_at=created_at,
            source_profiles=[SourceProfile(source_system=adapter.source_system, profile_version=adapter.profile_version)],
            source_versions=[SourceVersion(
                source_version_id=source_version_id, source_system=adapter.source_system,
                source_scope=source_scope, native_id=native_id, content_hash=source_hash,
                observed_at=created_at,
                storage=SourceNativeReference(
                    storage_kind="relative_path", relative_path=source_relative,
                    byte_length=len(data), hashes=[{"algorithm": "sha256", "digest": source_hash}],
                    role="source_export",
                ),
                access=access,
            )],
            parser=ParserDescriptor(name=adapter.name, version=adapter.version),
            adapter_contracts={adapter.name: adapter.contract_version},
            files=files, fidelity=fidelity,
        )
        (stage / "manifest.json").write_text(_serialize(manifest) + "\n", encoding="utf-8")
        return store.commit(stage, output_dir)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
