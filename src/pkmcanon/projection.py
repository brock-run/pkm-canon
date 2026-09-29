"""Audit-oriented Markdown projection with evidence and fidelity sidecars."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from .adapters import stable_id
from .evidence import evidence_for_node
from .models import FileInventoryEntry, ProjectionManifest
from .package import CanonicalPackage, PackageValidationError
from .schema_validation import default_schema_store

ADAPTER_NAME = "audit-markdown"
ADAPTER_VERSION = "0.1.0"


def _hash(data: bytes) -> str:
    """Return the hexadecimal SHA-256 digest used in the projection inventory."""
    return hashlib.sha256(data).hexdigest()


def _manifest_path(root: Path) -> Path:
    """Return the projection manifest path beneath the supplied root."""
    return root / "projection-manifest.json"


def _escape_continuation_markdown(line: str) -> str:
    if match := re.match(r"^([ \t]*)([!\"#$%&'()*+,\-./:;<=>?@\[\\\]^_`{|}~])", line):
        return f"{match.group(1)}\\{line[len(match.group(1)):]}"
    if match := re.match(r"^([ \t]*\d+)([.)])(?=\s)", line):
        return f"{match.group(1)}\\{match.group(2)}{line[match.end():]}"
    return line


def _render_node_text(text: str, continuation_indent: str) -> str:
    lines = text.split("\n")
    return lines[0] + "".join(
        f"\n{continuation_indent}{_escape_continuation_markdown(line)}"
        for line in lines[1:]
    )


def validate_projection(root: Path) -> ProjectionManifest:
    """Validate a projection manifest, file inventory, hashes, and record and issue counts."""
    root = Path(root)
    manifest_path = _manifest_path(root)
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    default_schema_store().validate_instance_with_short_name(raw, "projection-manifest")
    manifest = ProjectionManifest.model_validate(raw)
    actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()} - {"projection-manifest.json"}
    if actual != set(manifest.files):
        raise PackageValidationError("PROJECTION_INVENTORY_MISMATCH", str(root))
    for relative, entry in manifest.files.items():
        path = root / relative
        if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
            raise PackageValidationError("UNSAFE_PROJECTION_PATH", relative)
        data = path.read_bytes()
        if _hash(data) != entry.sha256 or len(data) != entry.byte_length:
            raise PackageValidationError("PROJECTION_HASH_MISMATCH", relative)
        if path.suffix == ".jsonl":
            actual_count = sum(bool(line.strip()) for line in data.splitlines())
            if entry.record_count != actual_count:
                raise PackageValidationError("PROJECTION_RECORD_COUNT_MISMATCH", relative)
        elif entry.record_count is not None:
            raise PackageValidationError("PROJECTION_RECORD_COUNT_MISMATCH", relative)
    issues = manifest.files.get("projection-issues.jsonl")
    if issues is None or issues.record_count != manifest.issue_count:
        raise PackageValidationError("PROJECTION_ISSUE_COUNT_MISMATCH", str(root))
    return manifest


def project_audit_markdown(package: CanonicalPackage, output_dir: Path) -> ProjectionManifest:
    """Publish a validated audit projection with evidence sidecars, reusing an identical projection."""
    output_dir = Path(output_dir)
    projection_id = stable_id("projection", package.manifest.package_id, ADAPTER_NAME, ADAPTER_VERSION)
    if output_dir.exists():
        manifest = validate_projection(output_dir)
        if manifest.projection_id == projection_id:
            return manifest
        raise PackageValidationError("PROJECTION_EXISTS", str(output_dir))
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=output_dir.parent))
    try:
        children: dict[str | None, list] = {}
        for node in package.nodes:
            children.setdefault(node.parent_node_id, []).append(node)
        for group in children.values():
            group.sort(key=lambda node: (node.position, node.node_id))
        evidence_map = []

        def append_nodes(
            document_id: str, filename: str, lines: list[str],
            parent: str | None, depth: int,
        ) -> None:
            """Append nested Markdown bullets and record their rendered-line evidence mappings."""
            for node in [item for item in children.get(parent, []) if item.document_id == document_id]:
                rendered_line = sum(line.count("\n") + 1 for line in lines) + 1
                text = _render_node_text(node.plain_text, "  " * (depth + 1))
                lines.append(f"{'  ' * depth}- {text}")
                evidence = evidence_for_node(package, node.node_id)
                evidence_map.append({
                    "page": filename, "rendered_line": rendered_line,
                    "node_id": node.node_id,
                    "source_version_id": evidence.source_version_id,
                    "source_locator": evidence.source_locator.model_dump(mode="json", exclude_none=True),
                    "source_content_hash": evidence.source_content_hash,
                })
                append_nodes(document_id, filename, lines, node.node_id, depth + 1)

        for document in sorted(package.documents, key=lambda item: item.document_id):
            filename = stable_id("page", document.document_id).split(":", 1)[1] + ".md"
            lines = [
                f"# {document.title}", "",
                f"Source package: {package.manifest.package_id}  ",
                f"Source document: {document.document_id}  ",
                f"Source version: {document.source_version_id}", "",
            ]

            append_nodes(document.document_id, filename, lines, None, 0)
            (stage / filename).write_text("\n".join(lines) + "\n", encoding="utf-8")
        (stage / "evidence-map.jsonl").write_text(
            "".join(json.dumps(item, sort_keys=True, ensure_ascii=False) + "\n" for item in evidence_map),
            encoding="utf-8",
        )
        issues = [
            {
                "diagnostic_id": item.diagnostic_id, "code": item.code,
                "subject_id": item.subject_id, "detail": item.detail,
            }
            for item in package.diagnostics
        ]
        (stage / "projection-issues.jsonl").write_text(
            "".join(json.dumps(item, sort_keys=True, ensure_ascii=False) + "\n" for item in issues),
            encoding="utf-8",
        )
        files = {}
        for path in sorted(stage.iterdir()):
            data = path.read_bytes()
            files[path.name] = FileInventoryEntry(
                sha256=_hash(data), byte_length=len(data),
                record_count=sum(bool(line.strip()) for line in data.splitlines()) if path.suffix == ".jsonl" else None,
            )
        manifest = ProjectionManifest(
            projection_id=projection_id, adapter_name=ADAPTER_NAME,
            adapter_contract_version=ADAPTER_VERSION,
            source_package_id=package.manifest.package_id,
            files=files, issue_count=len(issues),
        )
        raw = manifest.model_dump(mode="json", exclude_none=True)
        default_schema_store().validate_instance_with_short_name(raw, "projection-manifest")
        _manifest_path(stage).write_text(
            json.dumps(raw, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        validate_projection(stage)
        os.replace(stage, output_dir)
        return manifest
    finally:
        if stage.exists():
            shutil.rmtree(stage)
