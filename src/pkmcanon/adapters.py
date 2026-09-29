"""Versioned source-adapter contract and deterministic source identities."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Protocol

from pydantic import BaseModel

from .models import Diagnostic


def stable_id(prefix: str, *parts: str) -> str:
    """Return a prefixed identifier derived from the ordered parts using SHA-256."""
    encoded = json.dumps(parts, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return f"{prefix}:{hashlib.sha256(encoded).hexdigest()[:24]}"


@dataclass
class AdapterResult:
    records: list[BaseModel] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    source_object_count: int = 0


class SourceAdapter(Protocol):
    source_system: str
    profile_version: str
    name: str
    version: str
    contract_version: str

    def parse(self, data: bytes, *, source_scope: str, source_version_id: str, native_id: str) -> AdapterResult:
        """Convert source bytes and their identity into canonical records and diagnostics."""
        ...
