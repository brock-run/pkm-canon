"""Product-neutral canon store port and PKM Canon's package adapter."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TypeVar

from .package import CanonicalPackage, PackageValidationError

RefT_contra = TypeVar("RefT_contra", contravariant=True)
CommitT_contra = TypeVar("CommitT_contra", contravariant=True)
ArtifactT_co = TypeVar("ArtifactT_co", covariant=True)


class CanonStore(Protocol[RefT_contra, CommitT_contra, ArtifactT_co]):
    """Open and commit a product's own validated artifact.

    Ref, commit request, and return value belong to the product adapter. This
    port makes no assumptions about packages, databases, branches, or claims.
    """

    def open(self, ref: RefT_contra) -> ArtifactT_co:
        """Open and validate the product artifact at the supplied reference."""
        ...

    def commit(self, request: CommitT_contra) -> ArtifactT_co:
        """Commit a validated artifact and return its product-owned value."""
        ...


@dataclass(frozen=True)
class PackageCommit:
    staged: Path
    destination: Path


CanonicalStore = CanonStore[Path, PackageCommit, CanonicalPackage]


class FilesystemPackageStore:
    def open(self, location: Path) -> CanonicalPackage:
        """Load and validate a package from its filesystem directory."""
        return CanonicalPackage(location)

    def commit(self, request: PackageCommit) -> CanonicalPackage:
        """Validate and atomically move a staged package, reusing one with the same ID.

        Return the package at request.destination. Reusing an existing package
        leaves request.staged in place. Validation and read errors propagate;
        a different existing package raises PackageValidationError with code
        PACKAGE_EXISTS. A failed move raises PACKAGE_COMMIT_FAILED unless a
        valid destination with the same ID can be reused after the failure.
        """
        staged, destination = request.staged, request.destination
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
