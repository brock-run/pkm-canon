"""Canonical commit port and filesystem implementation for Rosetta."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from .package import CanonicalPackage, PackageValidationError


class CanonicalStore(Protocol):
    def open(self, location: Path) -> CanonicalPackage: ...
    def commit(self, staged: Path, destination: Path) -> CanonicalPackage: ...


class FilesystemPackageStore:
    def open(self, location: Path) -> CanonicalPackage:
        return CanonicalPackage(location)

    def commit(self, staged: Path, destination: Path) -> CanonicalPackage:
        candidate = CanonicalPackage(staged)
        if destination.exists():
            existing = CanonicalPackage(destination)
            if existing.manifest.package_id == candidate.manifest.package_id:
                return existing
            raise PackageValidationError("PACKAGE_EXISTS", str(destination))
        try:
            os.replace(staged, destination)
        except OSError as exc:
            if destination.exists():
                existing = CanonicalPackage(destination)
                if existing.manifest.package_id == candidate.manifest.package_id:
                    return existing
            raise PackageValidationError("PACKAGE_COMMIT_FAILED", str(exc)) from exc
        candidate.root = destination
        return candidate
