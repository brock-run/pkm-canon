"""Deterministic Roam JSON source adapter."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from pkmcanon.adapters import AdapterResult, stable_id
from pkmcanon.models import (
    Attribute,
    Diagnostic,
    Document,
    Node,
    PreservationRecord,
    Relation,
    SourceLocator,
    SourceNativeReference,
    Span,
)

PAGE_REF = re.compile(r"\[\[([^\]]+)\]\]")
BLOCK_REF = re.compile(r"\(\(([^)]+)\)\)")
TAG = re.compile(r"#(?:\[\[([^\]]+)\]\]|([A-Za-z0-9_-]+))")
ATTRIBUTE = re.compile(r"^(.+?)::\s*(.*)$")
EMBED = re.compile(r"\{\{(?:\[\[)?embed(?:\]\])?:\s*(?:\[\[([^\]]+)\]\]|\(\(([^)]+)\)\))\s*\}\}", re.IGNORECASE)
MACRO = re.compile(r"\{\{(.*?)\}\}")
RICH_TEXT = re.compile(r"\*\*|__|~~|\^\^")
PAGE_FIELDS = {"uid", "title", "create-time", "edit-time", "children"}
BLOCK_FIELDS = {"uid", "string", "order", "create-time", "edit-time", "children"}


def _timestamp(value: object) -> str | None:
    """Convert numeric epoch milliseconds to UTC, returning None for nonnumeric values."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(value / 1000, tz=UTC).isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def _raw_payload(value: dict) -> tuple[str, str]:
    """Return deterministic JSON text and its UTF-8 SHA-256 digest."""
    text = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


class RoamParser:
    source_system = "roam"
    profile_version = "0.1.0"
    name = "roam-json"
    version = "0.2.0"
    contract_version = "0.1.0"

    def __init__(self, source_graph_name: str | None = None):
        """Store an optional graph name for file-based parsing."""
        self.source_graph_name = source_graph_name

    def parse_file(self, filepath: Path, *, source_version_id: str = "source:uncommitted") -> AdapterResult:
        """Read a Roam export and parse it using the configured graph name or file stem."""
        return self.parse(filepath.read_bytes(), source_scope=self.source_graph_name or filepath.stem, source_version_id=source_version_id, native_id=filepath.name)

    def parse(self, data: bytes, *, source_scope: str, source_version_id: str, native_id: str) -> AdapterResult:
        """Convert Roam JSON pages into stable records with preservation and fidelity diagnostics."""
        try:
            pages = json.loads(data)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("INVALID_ROAM_JSON") from exc
        if not isinstance(pages, list) or not all(isinstance(page, dict) for page in pages):
            raise ValueError("INVALID_ROAM_ROOT")
        result = AdapterResult()
        seen_pages: set[str] = set()
        seen_blocks: set[str] = set()
        page_entries: list[tuple[dict, str, str, list[str]]] = []
        block_entries: list[tuple[dict, str, str, str, str | None, int, list[str]]] = []
        pages_by_title: dict[str, list[str]] = {}
        blocks_by_uid: dict[str, list[str]] = {}

        def key_for(value: dict, path: str, seen: set[str], issues: list[str]) -> str:
            """Use a unique UID or fall back to the JSON path while recording identity issues."""
            uid = value.get("uid")
            if not isinstance(uid, str) or not uid:
                issues.append("MISSING_UID")
                return f"path:{path}"
            if uid in seen:
                issues.append("DUPLICATE_UID")
                return f"path:{path}"
            seen.add(uid)
            return f"uid:{uid}"

        def scan_blocks(blocks: object, document_id: str, parent_id: str | None, parent_path: str) -> None:
            """Collect ordered block entries recursively and index their UIDs for reference lookup."""
            if not isinstance(blocks, list) or not all(isinstance(block, dict) for block in blocks):
                raise ValueError("INVALID_ROAM_CHILDREN")
            ordered = sorted(enumerate(blocks), key=lambda pair: (pair[1].get("order", 0) if isinstance(pair[1].get("order", 0), int) else 0, pair[0]))
            for position, (original_index, block) in enumerate(ordered):
                path = f"{parent_path}/children/{original_index}"
                issues: list[str] = []
                key = key_for(block, path, seen_blocks, issues)
                node_id = stable_id("node", self.source_system, source_scope, key)
                block_entries.append((block, node_id, document_id, path, parent_id, position, issues))
                uid = block.get("uid")
                if isinstance(uid, str) and uid:
                    blocks_by_uid.setdefault(uid, []).append(node_id)
                if "children" in block:
                    scan_blocks(block["children"], document_id, node_id, path)

        for index, page in enumerate(pages):
            path = f"/{index}"
            issues: list[str] = []
            key = key_for(page, path, seen_pages, issues)
            doc_id = stable_id("doc", self.source_system, source_scope, key)
            page_entries.append((page, doc_id, path, issues))
            title = page.get("title")
            if isinstance(title, str):
                pages_by_title.setdefault(title, []).append(doc_id)
            if "children" in page:
                scan_blocks(page["children"], doc_id, None, path)

        def preserve(subject_id: str, raw: dict, path: str, object_type: str) -> str:
            """Append a raw JSON preservation record and return its stable identifier."""
            text, digest = _raw_payload(raw)
            preservation_id = stable_id("pres", subject_id, path, digest)
            result.records.append(PreservationRecord(
                record_type="preservation_record", schema_version="0.1.0",
                id=preservation_id, subject_id=subject_id, source_system=self.source_system,
                source_profile_version=self.profile_version, source_object_type=object_type,
                source_locator=SourceLocator(graph=source_scope, path=path, source_uid=raw.get("uid") if isinstance(raw.get("uid"), str) else None),
                capture_type="raw_json",
                storage=SourceNativeReference(
                    storage_kind="embedded_utf8", inline_utf8=text, byte_length=len(text.encode("utf-8")),
                    hashes=[{"algorithm": "sha256", "digest": digest}], media_type="application/json", role="primary",
                ),
                normalization_status="partial", preservation_reason=["loss_prevention", "future_replay"],
            ))
            return preservation_id

        def diagnose(subject_id: str, raw: dict, path: str, issues: list[str], preservation_id: str | None) -> None:
            """Append one located diagnostic per distinct issue, linked to any preserved payload."""
            locator = SourceLocator(graph=source_scope, path=path, source_uid=raw.get("uid") if isinstance(raw.get("uid"), str) else None)
            for issue in sorted(set(issues)):
                result.diagnostics.append(Diagnostic(
                    diagnostic_id=stable_id("diag", subject_id, issue, path),
                    code=issue, severity="warning",
                    outcome="unresolved_reference" if issue.startswith("UNRESOLVED_") else "partial",
                    source_locator=locator, subject_id=subject_id,
                    preservation_id=preservation_id, detail=issue.replace("_", " ").lower(),
                ))

        def add_ref(
            node_id: str, issues: list[str], start: int, target: str,
            kind: str, representation: str, target_ids: list[str] | None,
            target_kind: str = "canonical",
        ) -> None:
            """Append a relation or record an issue when a canonical target cannot be resolved uniquely."""
            if target_kind == "canonical" and (target_ids is None or len(target_ids) != 1):
                issues.append(f"UNRESOLVED_{kind.upper()}")
                return
            result.records.append(Relation(
                relation_id=stable_id("rel", node_id, kind, str(start), target),
                source_id=node_id, target_id=target_ids[0] if target_kind == "canonical" else target,
                relation_type=kind, target_kind=target_kind, source_representation=representation,
            ))

        for page, doc_id, path, issues in page_entries:
            result.source_object_count += 1
            issues.extend(sorted(f"UNSUPPORTED_FIELD_{key}" for key in page.keys() - PAGE_FIELDS))
            if not isinstance(page.get("title"), str):
                issues.append("MISSING_TITLE")
            for field in ("create-time", "edit-time"):
                if field in page and _timestamp(page[field]) is None:
                    issues.append(f"INVALID_{field.upper().replace('-', '_')}")
            result.records.append(Document(
                document_id=doc_id, source_version_id=source_version_id, kind="page",
                title=page.get("title") if isinstance(page.get("title"), str) else "Untitled",
                created_at=_timestamp(page.get("create-time")), updated_at=_timestamp(page.get("edit-time")),
                facets={"pkm/source-roam": {
                    "_schemaURL": "urn:pkm-rosetta:facet:roam:v1",
                    "_producer": "roam-json:0.2.0",
                    "roam_uid": page.get("uid"),
                }},
            ))
            preservation_id = preserve(doc_id, page, path, "page") if issues else None
            diagnose(doc_id, page, path, issues, preservation_id)

        for block, node_id, doc_id, path, parent_id, position, issues in block_entries:
            result.source_object_count += 1
            issues.extend(sorted(f"UNSUPPORTED_FIELD_{key}" for key in block.keys() - BLOCK_FIELDS))
            if not isinstance(block.get("string"), str):
                issues.append("MISSING_STRING")
            if "order" in block and not isinstance(block["order"], int):
                issues.append("INVALID_ORDER")
            for field in ("create-time", "edit-time"):
                if field in block and _timestamp(block[field]) is None:
                    issues.append(f"INVALID_{field.upper().replace('-', '_')}")
            text = block.get("string") if isinstance(block.get("string"), str) else ""
            result.records.append(Node(
                node_id=node_id, document_id=doc_id, parent_node_id=parent_id,
                node_type="block", position=position, plain_text=text,
                facets={"pkm/source-roam": {
                    "_schemaURL": "urn:pkm-rosetta:facet:roam:v1",
                    "_producer": "roam-json:0.2.0",
                    "roam_uid": block.get("uid"),
                    "json_pointer": path,
                    "source_order": block.get("order"),
                    "created_at": _timestamp(block.get("create-time")),
                    "updated_at": _timestamp(block.get("edit-time")),
                }},
            ))
            result.records.append(Span(
                span_id=stable_id("span", node_id, "text", "0"), node_id=node_id,
                kind="text", text=text, start=0, end=len(text),
            ))

            match = ATTRIBUTE.match(text)
            if match:
                result.records.append(Attribute(
                    attribute_id=stable_id("attr", node_id, match.group(1).strip(), "0"),
                    subject_kind="node", subject_id=node_id, key=match.group(1).strip(),
                    value_type="string", value=match.group(2).strip(),
                ))

            covered: list[tuple[int, int]] = []
            for match in EMBED.finditer(text):
                covered.append(match.span())
                title, uid = match.groups()
                add_ref(node_id, issues, match.start(), title or uid, "embed", match.group(), pages_by_title.get(title) if title else blocks_by_uid.get(uid))
            for match in TAG.finditer(text):
                covered.append(match.span())
                tag = match.group(1) or match.group(2)
                add_ref(node_id, issues, match.start(), f"tag:{tag}", "tag", match.group(), None, "tag")
            for pattern, target_map, kind in ((PAGE_REF, pages_by_title, "page_ref"), (BLOCK_REF, blocks_by_uid, "block_ref")):
                for match in pattern.finditer(text):
                    if any(start <= match.start() < end for start, end in covered):
                        continue
                    add_ref(node_id, issues, match.start(), match.group(1), kind, match.group(), target_map.get(match.group(1)))
            for match in MACRO.finditer(text):
                if not EMBED.fullmatch(match.group()):
                    issues.append("UNSUPPORTED_MACRO")
            if RICH_TEXT.search(text) or chr(96) in text:
                issues.append("RICH_TEXT_NOT_NORMALIZED")
            preservation_id = preserve(node_id, block, path, "block") if issues else None
            diagnose(node_id, block, path, issues, preservation_id)
        return result
