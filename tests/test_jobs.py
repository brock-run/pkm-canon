import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pkmcanon.jobs import JobStore, create_app
from pkmcanon.package import CanonicalPackage, PackageValidationError


def test_job_api_upload_worker_and_dedup(tmp_path: Path) -> None:
    """Verify duplicate uploads share a job and the worker publishes a validated package."""
    root = tmp_path / "jobs"
    client = TestClient(create_app(root, max_upload_bytes=4096))
    payload = json.dumps([{"uid": "P", "title": "Page", "children": [{"uid": "B", "string": "Owner:: Team"}]}]).encode()
    query = "?source_scope=graph&native_id=export.json"
    first = client.post(f"/api/v1/ingest/roam{query}", content=payload, headers={"content-type": "application/json"})
    assert first.status_code == 202
    job_id = first.json()["job_id"]
    assert first.json()["state"] == "received"
    duplicate = client.post(f"/api/v1/ingest/roam{query}", content=payload, headers={"content-type": "application/json"})
    assert duplicate.json()["job_id"] == job_id
    assert len(list((root / "inputs").glob("*.json"))) == 1

    completed = JobStore(root).run_next()
    assert completed is not None and completed.state == "package_ready"
    assert completed.attempts == 1
    package = CanonicalPackage(root / "packages" / job_id)
    assert package.manifest.package_id == completed.package_id
    assert client.get(f"/api/v1/ingest/jobs/{job_id}").json()["state"] == "package_ready"
    assert JobStore(root).run_next() is None


def test_job_api_rejects_large_upload_and_marks_bad_source(tmp_path: Path) -> None:
    """Verify upload limits and durable, nonretryable errors for invalid source JSON."""
    root = tmp_path / "jobs"
    client = TestClient(create_app(root, max_upload_bytes=16))
    large = client.post(
        "/api/v1/ingest/roam?source_scope=graph&native_id=export.json",
        content=b"x" * 17,
    )
    assert large.status_code == 413
    assert JobStore(root).run_next() is None
    assert not list((root / "inputs").iterdir())

    bad = client.post(
        "/api/v1/ingest/roam?source_scope=graph&native_id=export.json",
        content=b"not json",
    )
    assert bad.status_code == 202
    failed = JobStore(root).run_next()
    assert failed is not None and failed.state == "failed"
    assert failed.error_code == "INVALID_ROAM_JSON"
    assert not failed.retryable
    assert client.post(f"/api/v1/ingest/jobs/{failed.job_id}/retry").status_code == 409


def test_expired_job_lease_can_resume_idempotently(tmp_path: Path) -> None:
    """Verify a worker reclaims an expired lease and completes the next attempt."""
    root = tmp_path / "jobs"
    store = JobStore(root)
    uploaded = root / "upload.tmp"
    uploaded.write_text("# Title\n\nOwner: Platform\n")
    job = store.enqueue(
        uploaded, source_type="markdown", source_scope="repo",
        native_id="docs/page.md", source_hash=hashlib.sha256(uploaded.read_bytes()).hexdigest(),
    )
    claimed = store.claim()
    assert claimed is not None and claimed.job_id == job.job_id
    with store._connection() as connection:
        connection.execute("UPDATE jobs SET lease_until = '2000-01-01T00:00:00+00:00' WHERE job_id = ?", (job.job_id,))
    completed = store.run_next()
    assert completed is not None and completed.state == "package_ready"
    assert completed.attempts == 2


@pytest.fixture
def queued_job(tmp_path):
    store = JobStore(tmp_path / "jobs")
    upload = tmp_path / "upload.md"
    upload.write_bytes(b"# Service\n\nOwner: Team\n")
    job = store.enqueue(upload, source_type="markdown", source_scope="repo", native_id="page.md", source_hash=hashlib.sha256(upload.read_bytes()).hexdigest())
    return store, job


def test_active_lease_prevents_second_worker_and_stale_worker_cannot_finish(queued_job):
    store, job = queued_job
    first = store.claim()
    assert first.job_id == job.job_id
    assert JobStore(store.root).claim() is None
    with store._connection() as connection:
        connection.execute("UPDATE jobs SET lease_until = ? WHERE job_id = ?", ("2000-01-01T00:00:00+00:00", job.job_id))
    second = store.claim()
    assert second.attempts == 2
    with pytest.raises(PackageValidationError, match="JOB_LEASE_LOST"):
        store.finish(first, package_id="stale")
    assert store.get(job.job_id).state == "running"
    store.finish(second, package_id="current")
    assert store.get(job.job_id).package_id == "current"


def test_missing_upload_can_retry_after_restoration(queued_job):
    store, job = queued_job
    path = store.inputs / f"{job.job_id}.md"
    data = path.read_bytes()
    path.unlink()
    failed = store.run_next()
    assert (failed.state, failed.error_code, failed.retryable) == ("failed", "UPLOAD_MISSING", True)
    assert store.run_next() is None
    path.write_bytes(data)
    retried = store.retry(job.job_id)
    assert (retried.state, retried.error_code, retried.retryable) == ("received", None, False)
    completed = store.run_next()
    assert (completed.state, completed.attempts) == ("package_ready", 2)
    assert store.retry(job.job_id) is None


def test_modified_upload_fails_without_retry_or_package(queued_job):
    store, job = queued_job
    (store.inputs / f"{job.job_id}.md").write_bytes(b"Changed source")
    failed = store.run_next()
    assert (failed.state, failed.error_code, failed.retryable) == ("failed", "UPLOAD_HASH_MISMATCH", False)
    assert store.retry(job.job_id) is None
    assert not list(store.packages.iterdir())


def test_unexpected_worker_error_is_sanitized_and_retryable(queued_job, monkeypatch):
    store, job = queued_job

    def fail(*args, **kwargs):
        raise RuntimeError("private internal details")

    monkeypatch.setattr("pkmcanon.jobs.build_package", fail)
    failed = store.run_next()
    assert (failed.error_code, failed.retryable) == ("INGESTION_FAILED", True)
    assert "private internal details" not in failed.model_dump_json()
    assert store.retry(job.job_id).state == "received"


@pytest.mark.parametrize("claimed_length", [None, "1"])
def test_streamed_upload_limit_is_enforced_without_trusting_content_length(tmp_path, claimed_length):
    root = tmp_path / "jobs"
    with TestClient(create_app(root, max_upload_bytes=4)) as client:
        headers = {} if claimed_length is None else {"content-length": claimed_length}
        response = client.post("/api/v1/ingest/markdown?source_scope=repo&native_id=p.md", content=iter([b"abc", b"de"]), headers=headers)
    assert response.status_code == 413
    assert response.json()["detail"] == "UPLOAD_TOO_LARGE"
    assert list((root / "inputs").iterdir()) == []
    assert JobStore(root).claim() is None


def test_upload_at_exact_limit_and_missing_job_routes(tmp_path):
    with TestClient(create_app(tmp_path / "jobs", max_upload_bytes=4)) as client:
        response = client.post("/api/v1/ingest/markdown?source_scope=repo&native_id=p.md", content=b"text")
        assert response.status_code == 202
        assert client.get("/api/v1/ingest/jobs/absent").status_code == 404
        assert client.post("/api/v1/ingest/jobs/absent/retry").status_code == 404
        assert client.post(f"/api/v1/ingest/jobs/{response.json()['job_id']}/retry").status_code == 409
    assert not list((tmp_path / "jobs" / "inputs").glob(".upload-*"))


@pytest.mark.parametrize("limit", [0, -1])
def test_upload_limit_must_be_positive(tmp_path, limit):
    with pytest.raises(ValueError, match="max_upload_bytes must be positive"):
        create_app(tmp_path / "jobs", max_upload_bytes=limit)
