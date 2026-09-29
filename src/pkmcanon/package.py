"""Validated, portable canonical packages."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import BaseModel

from .models import (
    Attribute,
    Diagnostic,
    Document,
    Manifest,
    Node,
    PreservationBundle,
    PreservationRecord,
    Relation,
    SourceNativeReference,
    Span,
)
from .schema_validation import default_schema_store

RECORD_FAMILIES: dict[str, tuple[type[BaseModel], str, str]] = {
    "documents.jsonl": (Document, "documents", "document_id"),
    "nodes.jsonl": (Node, "nodes", "node_id"),
    "spans.jsonl": (Span, "spans", "span_id"),
    "relations.jsonl": (Relation, "relations", "relation_id"),
    "attributes.jsonl": (Attribute, "attributes", "attribute_id"),
    "preservation_records.jsonl": (PreservationRecord, "preservation-record", "id"),
    "preservation_bundles.jsonl": (PreservationBundle, "preservation-bundle", "id"),
    "diagnostics.jsonl": (Diagnostic, "diagnostic", "diagnostic_id"),
}


class PackageValidationError(ValueError):
    def __init__(self, code: str, detail: str):
        """Store a machine-readable code and include its detail in the exception message."""
        self.code = code
        super().__init__(f"{code}: {detail}")


def _check(condition: bool, code: str, detail: str) -> None:
    """Raise a package validation error with the supplied code when a condition fails."""
    if not condition:
        raise PackageValidationError(code, detail)


def _safe_file(root: Path, relative: str) -> Path:
    """Resolve an existing package file while rejecting unsafe paths and file symlinks."""
    part = PurePosixPath(relative)
    _check(
        bool(relative) and not part.is_absolute() and ".." not in part.parts
        and "." not in part.parts and "\\" not in relative and part.as_posix() == relative,
        "UNSAFE_PATH",
        relative,
    )
    path = root / relative
    _check(not path.is_symlink() and path.resolve().is_relative_to(root.resolve()), "UNSAFE_PATH", relative)
    _check(path.is_file(), "MISSING_FILE", relative)
    return path


def _sha256(data: bytes) -> str:
    """Return the hexadecimal SHA-256 digest of the supplied bytes."""
    return hashlib.sha256(data).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read nonblank JSONL rows, rejecting malformed JSON and values that are not objects."""
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PackageValidationError("INVALID_JSONL", f"{path.name}:{number}: {exc}") from exc
        _check(isinstance(value, dict), "INVALID_JSONL", f"{path.name}:{number} is not an object")
        rows.append(value)
    return rows


def _validate_storage(root: Path, storage: SourceNativeReference) -> bytes | None:
    """Check local or embedded payload hashes and lengths; return None for external URIs."""
    if storage.storage_kind == "relative_path":
        data = _safe_file(root, storage.relative_path or "").read_bytes()
    elif storage.storage_kind == "embedded_utf8":
        data = (storage.inline_utf8 or "").encode("utf-8")
    elif storage.storage_kind == "embedded_base64":
        import base64
        import binascii

        try:
            data = base64.b64decode(storage.inline_base64 or "", validate=True)
        except binascii.Error as exc:
            raise PackageValidationError("INVALID_BASE64", str(exc)) from exc
    else:
        return None  # External references are recorded, never fetched by validation.
    if storage.byte_length is not None:
        _check(len(data) == storage.byte_length, "STORAGE_LENGTH_MISMATCH", str(storage.relative_path))
    for descriptor in storage.hashes:
        actual = hashlib.new(descriptor.algorithm, data).hexdigest()
        _check(actual == descriptor.digest, "STORAGE_HASH_MISMATCH", str(storage.relative_path))
    return data


class CanonicalPackage:
    def __init__(self, root: Path, *, validate: bool = True):
        """Load a package and validate it by default, or load only its manifest when disabled."""
        self.root = Path(root)
        self.manifest: Manifest
        self._rows: dict[str, list[BaseModel]] = {}
        if validate:
            self.validate()
        else:
            self.manifest = Manifest.model_validate_json((self.root / "manifest.json").read_text())

    def validate(self) -> CanonicalPackage:
        """Load and validate inventory, records, references, and fidelity, then return self."""
        root = self.root
        _check(root.is_dir(), "MISSING_PACKAGE", str(root))
        manifest_path = _safe_file(root, "manifest.json")
        try:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.manifest = Manifest.model_validate(manifest_data)
            default_schema_store().validate_instance_with_short_name(manifest_data, "manifest")
        except Exception as exc:
            if isinstance(exc, PackageValidationError):
                raise
            raise PackageValidationError("MANIFEST_INVALID", str(exc)) from exc

        inventory = self.manifest.files
        _check(all(name in inventory for name in RECORD_FAMILIES), "INVENTORY_MISSING_FAMILY", "record-family inventory incomplete")
        for relative in inventory:
            _safe_file(root, relative)
        actual_files = {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file() or path.is_symlink()
        } - {"manifest.json"}
        _check(actual_files == set(inventory), "INVENTORY_MISMATCH", "inventory differs from package files")

        store = default_schema_store()
        validators = {}
        rows: dict[str, list[BaseModel]] = {}
        all_ids: set[str] = set()
        for relative, entry in inventory.items():
            path = _safe_file(root, relative)
            content = path.read_bytes()
            _check(len(content) == entry.byte_length, "FILE_LENGTH_MISMATCH", relative)
            _check(_sha256(content) == entry.sha256, "FILE_HASH_MISMATCH", relative)
            if relative in RECORD_FAMILIES:
                model, schema_name, id_field = RECORD_FAMILIES[relative]
                raw_rows = _read_jsonl(path)
                _check(entry.record_count == len(raw_rows), "RECORD_COUNT_MISMATCH", relative)
                validator = validators.get(schema_name)
                if validator is None:
                    validator = store.validator_for_short_name(schema_name)
                    validators[schema_name] = validator
                parsed: list[BaseModel] = []
                for number, raw in enumerate(raw_rows, 1):
                    try:
                        validator.validate(raw)
                        item = model.model_validate(raw)
                    except Exception as exc:
                        raise PackageValidationError("RECORD_INVALID", f"{relative}:{number}: {exc}") from exc
                    identifier = getattr(item, id_field)
                    _check(identifier not in all_ids, "DUPLICATE_ID", identifier)
                    all_ids.add(identifier)
                    parsed.append(item)
                rows[relative] = parsed
            else:
                _check(entry.record_count is None, "INVENTORY_MISMATCH", f"{relative} is not JSONL")
        self._rows = rows
        self._validate_references()
        self._validate_fidelity()
        return self

    def _validate_references(self) -> None:
        """Check source integrity, record links, parent trees, spans, and preservation payloads."""
        root = self.root
        sources = {item.source_version_id: item for item in self.manifest.source_versions}
        _check(len(sources) == len(self.manifest.source_versions), "DUPLICATE_SOURCE_VERSION", "source version IDs repeat")
        for source in sources.values():
            data = _validate_storage(root, source.storage)
            _check(data is not None, "SOURCE_NOT_PRESERVED", source.source_version_id)
            _check(_sha256(data) == source.content_hash, "SOURCE_HASH_MISMATCH", source.source_version_id)
        docs = {item.document_id: item for item in self.documents}
        nodes = {item.node_id: item for item in self.nodes}
        spans = {item.span_id: item for item in self.spans}
        preservation = {item.id: item for item in self.preservation_records + self.preservation_bundles}
        for doc in docs.values():
            _check(doc.source_version_id in sources, "DANGLING_SOURCE_VERSION", doc.document_id)
        for node in nodes.values():
            _check(node.document_id in docs, "DANGLING_DOCUMENT", node.node_id)
            if node.parent_node_id is not None:
                _check(node.parent_node_id in nodes, "DANGLING_PARENT", node.node_id)
                _check(nodes[node.parent_node_id].document_id == node.document_id, "CROSS_DOCUMENT_PARENT", node.node_id)
            seen: set[str] = set()
            cursor = node
            while cursor.parent_node_id is not None:
                _check(cursor.node_id not in seen, "PARENT_CYCLE", node.node_id)
                seen.add(cursor.node_id)
                _check(cursor.parent_node_id in nodes, "DANGLING_PARENT", cursor.node_id)
                cursor = nodes[cursor.parent_node_id]
        for span in spans.values():
            _check(span.node_id in nodes, "DANGLING_NODE", span.span_id)
            if span.start is not None or span.end is not None:
                _check(span.start is not None and span.end is not None, "INVALID_SPAN_RANGE", span.span_id)
                _check(span.start <= span.end <= len(nodes[span.node_id].plain_text), "INVALID_SPAN_RANGE", span.span_id)
                _check(nodes[span.node_id].plain_text[span.start:span.end] == span.text, "SPAN_TEXT_MISMATCH", span.span_id)
        subjects = set(docs) | set(nodes)
        for relation in self.relations:
            _check(relation.source_id in subjects, "DANGLING_RELATION_SOURCE", relation.relation_id)
            if relation.target_kind == "canonical":
                _check(relation.target_id in subjects, "DANGLING_RELATION_TARGET", relation.relation_id)
        for attribute in self.attributes:
            _check(attribute.subject_id in subjects, "DANGLING_ATTRIBUTE_SUBJECT", attribute.attribute_id)
        for item in preservation.values():
            _check(item.subject_id in subjects, "DANGLING_PRESERVATION_SUBJECT", item.id)
            if isinstance(item, PreservationBundle) and item.primary_item_index is not None:
                _check(item.primary_item_index < len(item.bundle_items), "INVALID_PRIMARY_ITEM_INDEX", item.id)
            stores = [item.storage] if isinstance(item, PreservationRecord) else item.bundle_items
            for storage in stores:
                _validate_storage(root, storage)
        for diagnostic in self.diagnostics:
            if diagnostic.subject_id is not None:
                _check(diagnostic.subject_id in subjects, "DANGLING_DIAGNOSTIC_SUBJECT", diagnostic.diagnostic_id)
            if diagnostic.preservation_id is not None:
                _check(diagnostic.preservation_id in preservation, "DANGLING_DIAGNOSTIC_PRESERVATION", diagnostic.diagnostic_id)
            if diagnostic.outcome in {"partial", "preserved_only", "unsupported"}:
                _check(diagnostic.preservation_id is not None, "UNPRESERVED_OUTCOME", diagnostic.diagnostic_id)

    def _validate_fidelity(self) -> None:
        """Reconcile manifest fidelity totals with loaded records and diagnostics."""
        fidelity = self.manifest.fidelity
        _check(
            fidelity.source_object_count
            == fidelity.normalized + fidelity.partial + fidelity.preserved_only + fidelity.unsupported + fidelity.rejected,
            "FIDELITY_MISMATCH", "source object count",
        )
        diagnostics = self.diagnostics
        partial_subjects = {item.subject_id for item in diagnostics if item.outcome == "partial"}
        _check(None not in partial_subjects, "FIDELITY_MISMATCH", "partial diagnostic lacks subject")
        _check(fidelity.partial == len(partial_subjects), "FIDELITY_MISMATCH", "partial count")
        _check(fidelity.normalized == len(self.documents) + len(self.nodes) - len(partial_subjects), "FIDELITY_MISMATCH", "normalized count")
        for outcome in ("preserved_only", "unsupported", "rejected"):
            expected = len([item for item in diagnostics if item.outcome == outcome])
            _check(getattr(fidelity, outcome) == expected, "FIDELITY_MISMATCH", outcome)
        _check(fidelity.unresolved_reference_count == sum(item.outcome == "unresolved_reference" for item in diagnostics), "FIDELITY_MISMATCH", "unresolved references")
        _check(fidelity.warning_count == sum(item.severity == "warning" for item in diagnostics), "FIDELITY_MISMATCH", "warnings")
        _check(fidelity.error_count == sum(item.severity == "error" for item in diagnostics), "FIDELITY_MISMATCH", "errors")

    def _family(self, name: str):
        """Return the loaded records for a JSONL family filename."""
        return self._rows[name]

    @property
    def documents(self) -> list[Document]:
        """Return the loaded document records."""
        return self._family("documents.jsonl")

    @property
    def nodes(self) -> list[Node]:
        """Return the loaded content nodes."""
        return self._family("nodes.jsonl")

    @property
    def spans(self) -> list[Span]:
        """Return the loaded text spans."""
        return self._family("spans.jsonl")

    @property
    def relations(self) -> list[Relation]:
        """Return the loaded relation records."""
        return self._family("relations.jsonl")

    @property
    def attributes(self) -> list[Attribute]:
        """Return the loaded attribute records."""
        return self._family("attributes.jsonl")

    @property
    def preservation_records(self) -> list[PreservationRecord]:
        """Return the loaded individual preservation records."""
        return self._family("preservation_records.jsonl")

    @property
    def preservation_bundles(self) -> list[PreservationBundle]:
        """Return the loaded preservation bundles."""
        return self._family("preservation_bundles.jsonl")

    @property
    def preservation_artifacts(self) -> list[PreservationRecord | PreservationBundle]:
        """Return individual preservation records followed by preservation bundles."""
        return self.preservation_records + self.preservation_bundles

    @property
    def diagnostics(self) -> list[Diagnostic]:
        """Return the loaded ingestion diagnostics."""
        return self._family("diagnostics.jsonl")
