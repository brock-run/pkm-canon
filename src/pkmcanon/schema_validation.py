from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012


class SchemaStore:
    def __init__(self, schema_root: Path):
        self.schema_root = schema_root
        self._schemas_by_path: dict[Path, dict[str, Any]] = {}
        self._schemas_by_id: dict[str, dict[str, Any]] = {}
        self._paths_by_short_name: dict[str, Path] = {}
        self._validators_by_short_name: dict[str, Draft202012Validator] = {}
        self._registry = self._build_registry()

    def _load_schema_file(self, path: Path) -> dict[str, Any]:
        path = path.resolve()
        if path not in self._schemas_by_path:
            schema = json.loads(path.read_text(encoding="utf-8"))
            self._schemas_by_path[path] = schema
            schema_id = schema.get("$id")
            if schema_id:
                self._schemas_by_id[schema_id] = schema
        return self._schemas_by_path[path]

    def _iter_schema_files(self):
        return sorted(self.schema_root.rglob("*.json"))

    def _candidate_short_names(self, path: Path, schema: dict[str, Any]) -> list[str]:
        """Derive schema aliases from its filename, relative path, and optional title."""
        rel = path.relative_to(self.schema_root)
        stem = rel.stem
        stem = stem.removesuffix('.schema')
        rel_no_suffix = str(rel).replace('.schema.json', '').replace('.json', '')
        rel_no_suffix = rel_no_suffix.replace('\\', '/')
        names = {stem, rel_no_suffix, rel_no_suffix.replace('/', '.'), rel_no_suffix.replace('/', '-')}
        title = schema.get('title')
        if isinstance(title, str) and title.strip():
            names.add(title.strip())
        return sorted(n for n in names if n)

    def _register_short_names(self, path: Path, schema: dict[str, Any]) -> None:
        for name in self._candidate_short_names(path, schema):
            existing = self._paths_by_short_name.get(name)
            if existing is None:
                self._paths_by_short_name[name] = path.resolve()
            elif existing.resolve() != path.resolve():
                raise ValueError(f"Ambiguous schema short name '{name}' for {existing} and {path}")

    def _build_registry(self) -> Registry:
        registry = Registry()
        for path in self._iter_schema_files():
            schema = self._load_schema_file(path)
            self._register_short_names(path, schema)
            schema_id = schema.get("$id")
            if schema_id:
                resource = Resource(contents=schema, specification=DRAFT202012)
                registry = registry.with_resource(uri=schema_id, resource=resource)
        return registry

    def resolve_short_name(self, short_name: str) -> Path:
        if short_name not in self._paths_by_short_name:
            raise KeyError(f"Unknown schema short name: {short_name}")
        return self._paths_by_short_name[short_name]

    def schema_by_short_name(self, short_name: str) -> dict[str, Any]:
        return self._load_schema_file(self.resolve_short_name(short_name))

    def validator_for_short_name(self, short_name: str) -> Draft202012Validator:
        validator = self._validators_by_short_name.get(short_name)
        if validator is None:
            schema = self.schema_by_short_name(short_name)
            Draft202012Validator.check_schema(schema)
            validator = Draft202012Validator(schema, registry=self._registry)
            self._validators_by_short_name[short_name] = validator
        return validator

    def validate_instance_with_short_name(self, instance: Any, short_name: str) -> None:
        self.validator_for_short_name(short_name).validate(instance)

    def validate_jsonl_file(self, path: str | Path, short_name: str) -> None:
        file_path = Path(path)
        for line in file_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                self.validate_instance_with_short_name(json.loads(line), short_name)


def default_schema_store(schema_root: str | Path | None = None) -> SchemaStore:
    """Build a schema store from an explicit root or the repository schema directory."""
    if schema_root is None:
        schema_root = Path(__file__).resolve().parents[2] / "docs" / "specs" / "schemas"
    root = Path(schema_root)
    if not root.is_dir():
        raise FileNotFoundError(f"Schema root does not exist or is not a directory: {root}. Generate or restore docs/specs/schemas.")
    return SchemaStore(root)
