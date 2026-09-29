import shutil

import pytest

from pkmcanon.package import PackageValidationError
from pkmcanon.parsers.markdown import MarkdownAdapter
from pkmcanon.storage import FilesystemPackageStore
from pkmcanon.writer import build_package


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "source.md"
    path.write_text("# Service\n\nOwner: Team\n")
    return path


def test_writer_cleans_stage_and_does_not_publish_after_commit_failure(source, tmp_path):
    class FailingStore:
        staged = None

        def commit(self, staged, destination):
            self.staged = staged
            assert (staged / "manifest.json").is_file()
            raise OSError("disk full")

    store = FailingStore()
    output = tmp_path / "package"
    with pytest.raises(OSError, match="disk full"):
        build_package(MarkdownAdapter(), source, output, source_scope="repo", store=store)
    assert store.staged is not None and not store.staged.exists()
    assert not output.exists()
    assert not list(tmp_path.glob(".package.staging-*"))


def test_store_validates_before_publishing_and_keeps_existing_package(source, tmp_path):
    original = build_package(MarkdownAdapter(), source, tmp_path / "package", source_scope="repo")
    staged = tmp_path / "stage"
    shutil.copytree(original.root, staged)
    store = FilesystemPackageStore()
    assert store.commit(staged, original.root).root == original.root
    assert staged.exists()
    (staged / "nodes.jsonl").write_text("corrupt")
    destination = tmp_path / "new"
    with pytest.raises(PackageValidationError, match="FILE_LENGTH_MISMATCH"):
        store.commit(staged, destination)
    assert not destination.exists()
    assert store.open(original.root).manifest.package_id == original.manifest.package_id


def test_store_does_not_replace_different_existing_package(source, tmp_path):
    original = build_package(MarkdownAdapter(), source, tmp_path / "original", source_scope="repo")
    candidate = build_package(MarkdownAdapter(), source, tmp_path / "candidate", source_scope="other")
    with pytest.raises(PackageValidationError, match="PACKAGE_EXISTS"):
        FilesystemPackageStore().commit(candidate.root, original.root)
    assert FilesystemPackageStore().open(original.root).manifest.package_id == original.manifest.package_id
    assert candidate.root.exists()


def test_store_wraps_rename_failure_without_publishing(source, tmp_path, monkeypatch):
    staged = build_package(MarkdownAdapter(), source, tmp_path / "stage", source_scope="repo")

    def fail(*args):
        raise OSError("rename failed")

    monkeypatch.setattr("pkmcanon.storage.os.replace", fail)
    destination = tmp_path / "destination"
    with pytest.raises(PackageValidationError, match="PACKAGE_COMMIT_FAILED"):
        FilesystemPackageStore().commit(staged.root, destination)
    assert staged.root.exists()
    assert not destination.exists()


@pytest.mark.parametrize("same_package", [True, False], ids=["same-package", "conflicting-package"])
def test_store_handles_destination_created_during_atomic_commit(source, tmp_path, monkeypatch, same_package):
    staged = build_package(MarkdownAdapter(), source, tmp_path / "stage", source_scope="repo")
    winner = build_package(MarkdownAdapter(), source, tmp_path / "winner", source_scope="repo" if same_package else "other")
    destination = tmp_path / "destination"
    original_manifest = (winner.root / "manifest.json").read_bytes()

    def competing_commit(staged_path, destination_path):
        assert staged_path == staged.root
        assert destination_path == destination
        shutil.copytree(winner.root, destination_path)
        raise OSError("destination appeared during rename")

    monkeypatch.setattr("pkmcanon.storage.os.replace", competing_commit)
    store = FilesystemPackageStore()
    if same_package:
        committed = store.commit(staged.root, destination)
        assert committed.root == destination
        assert committed.manifest.package_id == staged.manifest.package_id
    else:
        with pytest.raises(PackageValidationError, match="PACKAGE_COMMIT_FAILED"):
            store.commit(staged.root, destination)
    assert (destination / "manifest.json").read_bytes() == original_manifest
    assert store.open(destination).manifest.package_id == winner.manifest.package_id
    assert staged.root.exists()


def test_idempotent_writer_does_not_parse_again(source, tmp_path, monkeypatch):
    adapter = MarkdownAdapter()
    package = build_package(adapter, source, tmp_path / "package", source_scope="repo")
    original = (package.root / "manifest.json").read_bytes()

    def unexpected_parse(*args, **kwargs):
        pytest.fail("An existing package with the same identity must be reused")

    monkeypatch.setattr(adapter, "parse", unexpected_parse)
    replay = build_package(adapter, source, package.root, source_scope="repo")
    assert replay.manifest == package.manifest
    assert (package.root / "manifest.json").read_bytes() == original
    assert not list(tmp_path.glob(".package.staging-*"))


def test_adapter_failure_leaves_no_package_or_staging_directory(source, tmp_path, monkeypatch):
    adapter = MarkdownAdapter()

    def fail(*args, **kwargs):
        raise ValueError("INVALID_SOURCE")

    monkeypatch.setattr(adapter, "parse", fail)
    with pytest.raises(ValueError, match="^INVALID_SOURCE$"):
        build_package(adapter, source, tmp_path / "package", source_scope="repo")
    assert not (tmp_path / "package").exists()
    assert not list(tmp_path.glob(".package.staging-*"))
