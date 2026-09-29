import json
from pathlib import Path

from fastapi.testclient import TestClient

from pkmcanon.jobs import JobStore, create_app
from pkmcanon.package import CanonicalPackage


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
    import hashlib

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
