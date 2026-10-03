import shutil

import pytest

from pkmcanon.package import PackageValidationError
from pkmcanon.parsers.markdown import MarkdownAdapter
from pkmcanon.storage import FilesystemPackageStore, PackageCommit
from pkmcanon.writer import build_package


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "source.md"
    path.write_text("# Service\n\nOwner: Team\n")
    return path


def test_writer_cleans_stage_and_does_not_publish_after_commit_failure(source, tmp_path):
    """Verify a failed commit leaves neither a published package nor staging files."""
    class FailingStore:
        staged = None

        def commit(self, request):
            """Capture the staged package path and simulate a disk-full commit failure."""
            self.staged = request.staged
            assert (request.staged / "manifest.json").is_file()
            raise OSError("disk full")

    store = FailingStore()
    output = tmp_path / "package"
    with pytest.raises(OSError, match="disk full"):
        build_package(MarkdownAdapter(), source, output, source_scope="repo", store=store)
    assert store.staged is not None and not store.staged.exists()
    assert not output.exists()
    assert not list(tmp_path.glob(".package.staging-*"))


def test_store_validates_before_publishing_and_keeps_existing_package(source, tmp_path):
    """Verify same-ID reuse preserves staging and corrupt packages are not published."""
    original = build_package(MarkdownAdapter(), source, tmp_path / "package", source_scope="repo")
    staged = tmp_path / "stage"
    shutil.copytree(original.root, staged)
    store = FilesystemPackageStore()
    assert store.commit(PackageCommit(staged, original.root)).root == original.root
    assert staged.exists()
    (staged / "nodes.jsonl").write_text("corrupt")
    destination = tmp_path / "new"
    with pytest.raises(PackageValidationError, match="FILE_LENGTH_MISMATCH"):
        store.commit(PackageCommit(staged, destination))
    assert not destination.exists()
    assert store.open(original.root).manifest.package_id == original.manifest.package_id


def test_store_does_not_replace_different_existing_package(source, tmp_path):
    """Verify a conflicting package ID leaves both existing and staged packages intact."""
    original = build_package(MarkdownAdapter(), source, tmp_path / "original", source_scope="repo")
    candidate = build_package(MarkdownAdapter(), source, tmp_path / "candidate", source_scope="other")
    with pytest.raises(PackageValidationError, match="PACKAGE_EXISTS"):
        FilesystemPackageStore().commit(PackageCommit(candidate.root, original.root))
    assert FilesystemPackageStore().open(original.root).manifest.package_id == original.manifest.package_id
    assert candidate.root.exists()


def test_parser_revision_cannot_reuse_prior_package_identity(source, tmp_path):
    """Keep source identity stable while a changed parser output gets a new package ID."""
    class PriorMarkdownAdapter(MarkdownAdapter):
        version = "0.1.0"

    prior = build_package(PriorMarkdownAdapter(), source, tmp_path / "prior", source_scope="repo")
    current = build_package(MarkdownAdapter(), source, tmp_path / "current", source_scope="repo")
    assert prior.manifest.source_versions[0].source_version_id == current.manifest.source_versions[0].source_version_id
    assert prior.manifest.package_id != current.manifest.package_id
    with pytest.raises(PackageValidationError, match="PACKAGE_EXISTS"):
        build_package(MarkdownAdapter(), source, prior.root, source_scope="repo")


def test_store_wraps_rename_failure_without_publishing(source, tmp_path, monkeypatch):
    """Verify rename errors become package errors without publishing or losing staging."""
    staged = build_package(MarkdownAdapter(), source, tmp_path / "stage", source_scope="repo")

    def fail(*args):
        raise OSError("rename failed")

    monkeypatch.setattr("pkmcanon.storage.os.replace", fail)
    destination = tmp_path / "destination"
    with pytest.raises(PackageValidationError, match="PACKAGE_COMMIT_FAILED"):
        FilesystemPackageStore().commit(PackageCommit(staged.root, destination))
    assert staged.root.exists()
    assert not destination.exists()
