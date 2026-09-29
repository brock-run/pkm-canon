"""Small repository-document adapter using the same package contract as Roam."""

from __future__ import annotations

import hashlib
import re

from pkmcanon.adapters import AdapterResult, stable_id
from pkmcanon.models import (
    Diagnostic,
    Document,
    Node,
    PreservationRecord,
    Relation,
    SourceLocator,
    SourceNativeReference,
    Span,
)

LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
HEADING = re.compile(r"^(#{1,6})\s+(.+)$")


class MarkdownAdapter:
    source_system = "markdown"
    profile_version = "0.1.0"
    name = "repository-markdown"
    version = "0.1.0"
    contract_version = "0.1.0"

    def parse(self, data: bytes, *, source_scope: str, source_version_id: str, native_id: str) -> AdapterResult:
        """Parse UTF-8 Markdown into records, preserving text for partially normalized structures."""
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("INVALID_MARKDOWN_ENCODING") from exc
        lines = text.splitlines()
        title = next((match.group(2) for line in lines if (match := HEADING.match(line))), native_id)
        doc_id = stable_id("doc", self.source_system, source_scope, native_id)
        result = AdapterResult()
        result.records.append(Document(
            document_id=doc_id, source_version_id=source_version_id,
            kind="markdown", title=title,
            facets={"pkm/source-markdown": {
                "_schemaURL": "urn:pkm-rosetta:facet:markdown:v1",
                "_producer": "repository-markdown:0.1.0",
                "path": native_id,
            }},
        ))
        result.source_object_count = 1
        blocks: list[tuple[int, int, str]] = []
        start = 0
        buffer: list[str] = []
        for index, line in enumerate(lines, 1):
            if not line.strip():
                if buffer:
                    blocks.append((start, index - 1, "\n".join(buffer)))
                    buffer = []
                continue
            if HEADING.match(line) and buffer:
                blocks.append((start, index - 1, "\n".join(buffer)))
                buffer = []
            if not buffer:
                start = index
            buffer.append(line)
            if HEADING.match(line):
                blocks.append((start, index, line))
                buffer = []
        if buffer:
            blocks.append((start, len(lines), "\n".join(buffer)))

        partial_reasons: list[str] = []
        for position, (line_start, line_end, block) in enumerate(blocks):
            node_id = stable_id("node", self.source_system, source_scope, native_id, str(line_start))
            heading = HEADING.match(block)
            kind = "heading" if heading else "block"
            if block.startswith((chr(96) * 3, "~~~")):
                kind = "code"
                partial_reasons.append("CODE_STRUCTURE_NOT_NORMALIZED")
            if any(line.lstrip().startswith("|") for line in block.splitlines()):
                partial_reasons.append("TABLE_STRUCTURE_NOT_NORMALIZED")
            if line_start == 1 and block.startswith("---"):
                partial_reasons.append("FRONTMATTER_NOT_NORMALIZED")
            if any(line.lstrip().startswith("<") for line in block.splitlines()):
                partial_reasons.append("HTML_NOT_NORMALIZED")
            result.records.append(Node(
                node_id=node_id, document_id=doc_id, node_type=kind,
                semantic_kind=kind, position=position, plain_text=block,
                facets={"pkm/source-markdown": {
                    "_schemaURL": "urn:pkm-rosetta:facet:markdown:v1",
                    "_producer": "repository-markdown:0.1.0",
                    "line_start": line_start, "line_end": line_end,
                }},
            ))
            result.records.append(Span(
                span_id=stable_id("span", node_id, "text"), node_id=node_id,
                kind="text", text=block, start=0, end=len(block),
            ))
            for match in LINK.finditer(block):
                result.records.append(Relation(
                    relation_id=stable_id("rel", node_id, "link", str(match.start()), match.group(2)),
                    source_id=node_id, target_id=match.group(2), target_kind="external",
                    relation_type="link", source_representation=match.group(),
                ))
            result.source_object_count += 1

        if partial_reasons:
            digest = hashlib.sha256(data).hexdigest()
            preservation_id = stable_id("pres", doc_id, digest)
            result.records.append(PreservationRecord(
                record_type="preservation_record", schema_version="0.1.0",
                id=preservation_id, subject_id=doc_id, source_system=self.source_system,
                source_profile_version=self.profile_version, source_object_type="markdown_document",
                source_locator=SourceLocator(workspace=source_scope, path=native_id),
                capture_type="raw_markdown",
                storage=SourceNativeReference(
                    storage_kind="embedded_utf8", inline_utf8=text,
                    byte_length=len(data), hashes=[{"algorithm": "sha256", "digest": digest}],
                    media_type="text/markdown", role="primary",
                ),
                normalization_status="partial", preservation_reason=["loss_prevention", "future_replay"],
            ))
            for reason in sorted(set(partial_reasons)):
                result.diagnostics.append(Diagnostic(
                    diagnostic_id=stable_id("diag", doc_id, reason),
                    code=reason, severity="warning", outcome="partial",
                    source_locator=SourceLocator(workspace=source_scope, path=native_id),
                    subject_id=doc_id, preservation_id=preservation_id,
                    detail="Source text is retained; this Markdown structure is not fully normalized",
                ))
        return result
