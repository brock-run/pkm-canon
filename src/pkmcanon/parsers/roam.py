import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from pydantic import BaseModel
from pkmcanon.models import (
    Document, Node, Relation, Attribute,
    PreservationRecord, SourceLocator, SourceNativeReference
)

# Regex patterns for Roam conventions
PAGE_REF_PATTERN = re.compile(r'\[\[(.*?)\]\]')
TAG_PATTERN = re.compile(r'#([A-Za-z0-9_-]+)|#\[\[(.*?)\]\]')
BLOCK_REF_PATTERN = re.compile(r'\(\((.*?)\)\)')
ATTRIBUTE_PATTERN = re.compile(r'^(.+?)::\s*(.*)')
# Handles {{embed: [[Page]]}} or {{[[embed]]: ((block))}}
EMBED_PATTERN = re.compile(r'\{\{(?:\[\[)?embed(?:\]\])?:\s*(?:\[\[(.*?)\]\]|\(\((.*?)\)\))\s*\}\}')
# Match macros that are NOT embeds to preserve them
COMPLEX_MACRO_PATTERN = re.compile(r'\{\{(?!/?(?:embed|\[\[embed\]\])).*?\}\}')

class RoamParser:
    """Parses Roam Research JSON exports into the PKM Canonical Package format."""

    def __init__(self, source_graph_name: str):
        self.source_graph_name = source_graph_name
        self.system_name = "roam"

    def _to_iso(self, timestamp_ms: int | None) -> str:
        """Convert Roam epoch ms to ISO 8601 string."""
        if not timestamp_ms:
            return datetime.now(timezone.utc).isoformat()
        return datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc).isoformat()

    def parse_file(self, filepath: Path) -> Iterator[BaseModel]:
        """Reads a Roam JSON file and yields canonical Pydantic models."""
        with open(filepath, 'r', encoding='utf-8') as f:
            roam_data = json.load(f)

        for page in roam_data:
            yield from self._parse_page(page)

    def _parse_page(self, page: dict) -> Iterator[BaseModel]:
        source_uid = page.get('uid', str(uuid.uuid4()))
        doc_id = f"doc:{self.system_name}:{self.source_graph_name}:{source_uid}"

        yield Document(
            document_id=doc_id,
            kind="page",
            title=page.get('title', 'Untitled'),
            created_at=self._to_iso(page.get('create-time')),
            updated_at=self._to_iso(page.get('edit-time')),
            facets={
                "pkm/source-roam": {
                    "_schemaURL": "https://example.org/schemas/facets/source-roam.json",
                    "roam_uid": source_uid
                }
            }
        )

        if 'children' in page:
            yield from self._parse_blocks(page['children'], doc_id, None)

    def _parse_blocks(self, blocks: list[dict], doc_id: str, parent_node_id: str | None) -> Iterator[BaseModel]:
        # Roam 'order' dictates vertical layout position
        sorted_blocks = sorted(blocks, key=lambda b: b.get('order', 0))

        for position, block in enumerate(sorted_blocks):
            source_uid = block.get('uid', str(uuid.uuid4()))
            node_id = f"node:{self.system_name}:{self.source_graph_name}:{source_uid}"
            text = block.get('string', '')

            yield Node(
                node_id=node_id,
                document_id=doc_id,
                parent_node_id=parent_node_id,
                node_type="block",
                position=position,
                plain_text=text
            )

            # Attributes (Key:: Value)
            attr_match = ATTRIBUTE_PATTERN.match(text)
            if attr_match:
                key, value = attr_match.groups()
                yield Attribute(
                    attribute_id=f"attr:{uuid.uuid4()}",
                    subject_kind="node",
                    subject_id=node_id,
                    key=key.strip(),
                    value_type="string",
                    value=value.strip()
                )

            # Embeds (Yielded strictly as relations per architectural constraint)
            for page_embed, block_embed in EMBED_PATTERN.findall(text):
                target = page_embed or block_embed
                target_id = f"doc:{self.system_name}:{self.source_graph_name}:{target}" if page_embed else f"node:{self.system_name}:{self.source_graph_name}:{target}"
                yield Relation(
                    relation_id=f"rel:{uuid.uuid4()}",
                    source_id=node_id,
                    target_id=target_id,
                    relation_type="embed",
                    source_representation=f"{{{{embed: {target}}}}}"
                )

            # Standard Page Refs
            for match in PAGE_REF_PATTERN.findall(text):
                yield Relation(
                    relation_id=f"rel:{uuid.uuid4()}",
                    source_id=node_id,
                    target_id=f"doc:{self.system_name}:{self.source_graph_name}:{match}",
                    relation_type="page_ref",
                    source_representation=f"[[{match}]]"
                )

            # Block Refs
            for match in BLOCK_REF_PATTERN.findall(text):
                yield Relation(
                    relation_id=f"rel:{uuid.uuid4()}",
                    source_id=node_id,
                    target_id=f"node:{self.system_name}:{self.source_graph_name}:{match}",
                    relation_type="block_ref",
                    source_representation=f"(({match}))"
                )

            # Tags
            for tag1, tag2 in TAG_PATTERN.findall(text):
                tag = tag1 or tag2
                yield Relation(
                    relation_id=f"rel:{uuid.uuid4()}",
                    source_id=node_id,
                    target_id=f"tag:{tag}",
                    relation_type="tag",
                    source_representation=f"#{tag}"
                )

            # Preserve Unsupported Macros (Queries, Calculators, Sliders)
            if COMPLEX_MACRO_PATTERN.search(text):
                yield PreservationRecord(
                    record_type="preservation_record",
                    schema_version="0.1.0",
                    id=f"pres:{uuid.uuid4()}",
                    subject_id=node_id,
                    source_system=self.system_name,
                    source_object_type="block_macro",
                    capture_type="plain_text",
                    storage=SourceNativeReference(
                        storage_kind="embedded_utf8",
                        inline_utf8=text,
                        role="source_export"
                    ),
                    normalization_status="partial",
                    preservation_reason=["unsupported_feature"]
                )

            if 'children' in block:
                yield from self._parse_blocks(block['children'], doc_id, node_id)