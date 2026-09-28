from __future__ import annotations
from pathlib import Path
import json
from .models import (
    Manifest,
    Document,
    Node,
    Span,
    Relation,
    Attribute,
    PreservationRecord,
    PreservationBundle,
    preservation_artifact_adapter,
)


def _read_json(path: Path):
    return json.loads(path.read_text())


def _read_jsonl(path: Path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _load_models(path: Path, model):
    return [model.model_validate(row) for row in _read_jsonl(path)]


class CanonicalPackage:
    def __init__(self, root: Path):
        self.root = root
        self.manifest = Manifest.model_validate(_read_json(root / "manifest.json"))

    @property
    def documents(self) -> list[Document]:
        return _load_models(self.root / "documents.jsonl", Document)

    @property
    def nodes(self) -> list[Node]:
        return _load_models(self.root / "nodes.jsonl", Node)

    @property
    def spans(self) -> list[Span]:
        return _load_models(self.root / "spans.jsonl", Span)

    @property
    def relations(self) -> list[Relation]:
        return _load_models(self.root / "relations.jsonl", Relation)

    @property
    def attributes(self) -> list[Attribute]:
        return _load_models(self.root / "attributes.jsonl", Attribute)

    @property
    def preservation_records(self) -> list[PreservationRecord]:
        return _load_models(self.root / "preservation_records.jsonl", PreservationRecord)

    @property
    def preservation_bundles(self) -> list[PreservationBundle]:
        return _load_models(self.root / "preservation_bundles.jsonl", PreservationBundle)

    @property
    def preservation_artifacts(self):
        rows = []
        for rel in ["preservation_records.jsonl", "preservation_bundles.jsonl"]:
            rows.extend(_read_jsonl(self.root / rel))
        return [preservation_artifact_adapter.validate_python(row) for row in rows]
