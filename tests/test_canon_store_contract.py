from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

import pytest

from pkmcanon.package import CanonicalPackage, PackageValidationError
from pkmcanon.storage import CanonStore, FilesystemPackageStore, PackageCommit

RefT = TypeVar("RefT")
CommitT = TypeVar("CommitT")
ArtifactT = TypeVar("ArtifactT")


def round_trip(
    store: CanonStore[RefT, CommitT, ArtifactT], request: CommitT, ref: RefT
) -> tuple[ArtifactT, ArtifactT]:
    return store.commit(request), store.open(ref)


def test_rosetta_store_validates_and_reopens_package(tmp_path: Path) -> None:
    import shutil

    staged = tmp_path / "staged"
    destination = tmp_path / "published"
    shutil.copytree("examples/minimal-package", staged)
    committed, reopened = round_trip(
        FilesystemPackageStore(), PackageCommit(staged, destination), destination
    )
    assert isinstance(committed, CanonicalPackage)
    assert committed.manifest.package_id == reopened.manifest.package_id
    assert committed.root == destination
    with pytest.raises(PackageValidationError, match="PACKAGE_EXISTS"):
        other = tmp_path / "other"
        shutil.copytree("examples/minimal-package", other)
        (other / "manifest.json").write_text(
            (other / "manifest.json").read_text().replace("pkg_demo_001", "pkg_other")
        )
        FilesystemPackageStore().commit(PackageCommit(other, destination))


@dataclass(frozen=True)
class StoryVersion:
    version_id: str


@dataclass(frozen=True)
class StoryCommit:
    version: StoryVersion


class StoryStore:
    def __init__(self) -> None:
        self.versions: dict[str, StoryVersion] = {}

    def open(self, ref: str) -> StoryVersion:
        return self.versions[ref]

    def commit(self, request: StoryCommit) -> StoryVersion:
        self.versions[request.version.version_id] = request.version
        return request.version


def test_port_returns_product_artifact_without_package_shape() -> None:
    store: CanonStore[str, StoryCommit, StoryVersion] = StoryStore()
    version = StoryVersion("character-elara-v2")
    committed, reopened = round_trip(store, StoryCommit(version), version.version_id)
    assert committed == reopened == version
