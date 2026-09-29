"""Local durable ingestion jobs: bounded upload, SQLite queue, separate worker."""

from __future__ import annotations

import hashlib
import os
import sqlite3
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict

from .adapters import stable_id
from .package import PackageValidationError
from .parsers.markdown import MarkdownAdapter
from .parsers.roam import RoamParser
from .writer import build_package

SourceType = Literal["roam", "markdown"]
_ADAPTERS = {"roam": RoamParser, "markdown": MarkdownAdapter}
_SUFFIXES = {"roam": ".json", "markdown": ".md"}
_RETRYABLE = {"INGESTION_FAILED", "UPLOAD_MISSING"}


def _now() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(UTC).isoformat()


class IngestionJob(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    state: Literal["received", "running", "package_ready", "failed"]
    source_type: SourceType
    source_scope: str
    native_id: str
    source_hash: str
    attempts: int
    created_at: str
    updated_at: str
    package_id: str | None = None
    error_code: str | None = None
    retryable: bool = False


class JobStore:
    """One local worker may process a job at a time; expired leases permit recovery."""

    def __init__(self, root: Path):
        """Create local input and package directories and initialize the SQLite job table."""
        self.root = Path(root)
        self.inputs = self.root / "inputs"
        self.packages = self.root / "packages"
        self.inputs.mkdir(parents=True, exist_ok=True)
        self.packages.mkdir(parents=True, exist_ok=True)
        self.database = self.root / "jobs.sqlite3"
        with self._connection() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_scope TEXT NOT NULL,
                    native_id TEXT NOT NULL,
                    source_hash TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    lease_until TEXT,
                    package_id TEXT,
                    error_code TEXT,
                    retryable INTEGER NOT NULL DEFAULT 0
                )
            """)

    def _connection(self) -> sqlite3.Connection:
        """Open the job database with named-column rows and a ten-second lock timeout."""
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _public(row: sqlite3.Row) -> IngestionJob:
        """Convert a database row to the public job model, excluding internal lease fields."""
        return IngestionJob.model_validate({
            key: row[key] for key in IngestionJob.model_fields
        })

    def get(self, job_id: str) -> IngestionJob | None:
        """Return the stored job, or None when its ID is unknown."""
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return self._public(row) if row else None

    def enqueue(
        self, temporary: Path, *, source_type: SourceType, source_scope: str,
        native_id: str, source_hash: str,
    ) -> IngestionJob:
        """Retain an upload and create or reuse a job keyed by source and adapter identity."""
        adapter = _ADAPTERS[source_type]()
        job_id = stable_id(
            "job", source_type, source_scope, native_id, source_hash,
            adapter.name, adapter.version, adapter.profile_version, adapter.contract_version,
            "private:local-operator",
        )
        destination = self.inputs / f"{job_id}{_SUFFIXES[source_type]}"
        try:
            os.link(temporary, destination)
        except FileExistsError:
            if hashlib.sha256(destination.read_bytes()).hexdigest() != source_hash:
                raise PackageValidationError("UPLOAD_HASH_CONFLICT", job_id) from None
        created_at = _now()
        with self._connection() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO jobs
                (job_id, state, source_type, source_scope, native_id, source_hash,
                 attempts, created_at, updated_at)
                VALUES (?, 'received', ?, ?, ?, ?, 0, ?, ?)""",
                (job_id, source_type, source_scope, native_id, source_hash, created_at, created_at),
            )
        job = self.get(job_id)
        if job is None:
            raise PackageValidationError("JOB_NOT_SAVED", job_id)
        return job

    def claim(self) -> IngestionJob | None:
        """Atomically lease the oldest queued or expired job for five minutes, if any."""
        now = _now()
        lease_until = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT * FROM jobs
                WHERE state = 'received' OR (state = 'running' AND lease_until < ?)
                ORDER BY created_at, job_id LIMIT 1""",
                (now,),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                """UPDATE jobs SET state = 'running', attempts = attempts + 1,
                   updated_at = ?, lease_until = ?, error_code = NULL, retryable = 0
                   WHERE job_id = ?""",
                (now, lease_until, row["job_id"]),
            )
            updated = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (row["job_id"],)).fetchone()
        return self._public(updated)

    def finish(self, job: IngestionJob, *, package_id: str | None = None, error_code: str | None = None) -> None:
        """Record success or failure for the claimed attempt, rejecting a lost lease."""
        with self._connection() as connection:
            changed = connection.execute(
                """UPDATE jobs SET state = ?, updated_at = ?, lease_until = NULL,
                   package_id = ?, error_code = ?, retryable = ?
                   WHERE job_id = ? AND state = 'running' AND attempts = ?""",
                (
                    "failed" if error_code else "package_ready", _now(), package_id,
                    error_code, int(error_code in _RETRYABLE), job.job_id, job.attempts,
                ),
            ).rowcount
        if changed != 1:
            raise PackageValidationError("JOB_LEASE_LOST", job.job_id)

    def retry(self, job_id: str) -> IngestionJob | None:
        """Requeue a retryable failed job, returning None if no job qualifies."""
        with self._connection() as connection:
            changed = connection.execute(
                """UPDATE jobs SET state = 'received', updated_at = ?,
                   error_code = NULL, retryable = 0
                   WHERE job_id = ? AND state = 'failed' AND retryable = 1""",
                (_now(), job_id),
            ).rowcount
        return self.get(job_id) if changed else None

    def run_next(self) -> IngestionJob | None:
        """Process one available job and persist its package ID or failure code."""
        job = self.claim()
        if job is None:
            return None
        source = self.inputs / f"{job.job_id}{_SUFFIXES[job.source_type]}"
        try:
            if not source.is_file():
                raise PackageValidationError("UPLOAD_MISSING", job.job_id)
            if hashlib.sha256(source.read_bytes()).hexdigest() != job.source_hash:
                raise PackageValidationError("UPLOAD_HASH_MISMATCH", job.job_id)
            package = build_package(
                _ADAPTERS[job.source_type](), source,
                self.packages / job.job_id,
                source_scope=job.source_scope, native_id=job.native_id,
            )
        except PackageValidationError as exc:
            self.finish(job, error_code=exc.code)
        except ValueError as exc:
            code = str(exc)
            self.finish(job, error_code=code if code.startswith("INVALID_") else "SOURCE_INVALID")
        except Exception:  # noqa: BLE001 - durable workers record a safe code for unexpected failures
            self.finish(job, error_code="INGESTION_FAILED")
        else:
            self.finish(job, package_id=package.manifest.package_id)
        return self.get(job.job_id)


def create_app(root: Path, *, max_upload_bytes: int = 32 * 1024 * 1024) -> FastAPI:
    """Create a local-only transport; deploy behind authentication if exposed."""
    if max_upload_bytes < 1:
        raise ValueError("max_upload_bytes must be positive")
    store = JobStore(root)
    app = FastAPI(title="PKM Rosetta ingestion", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        """Return the local API health response."""
        return {"status": "ok"}

    @app.post("/api/v1/ingest/{source_type}", response_model=IngestionJob, status_code=202)
    async def ingest(
        source_type: SourceType,
        request: Request,
        source_scope: Annotated[str, Query(min_length=1, max_length=200)],
        native_id: Annotated[str, Query(min_length=1, max_length=500)],
    ) -> IngestionJob:
        """Stream a size-limited upload into the queue and remove its temporary file."""
        claimed_length = request.headers.get("content-length")
        if claimed_length and claimed_length.isdecimal() and int(claimed_length) > max_upload_bytes:
            raise HTTPException(status_code=413, detail="UPLOAD_TOO_LARGE")
        descriptor, name = tempfile.mkstemp(prefix=".upload-", dir=store.inputs)
        temporary = Path(name)
        digest = hashlib.sha256()
        size = 0
        try:
            with os.fdopen(descriptor, "wb") as stream:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > max_upload_bytes:
                        raise HTTPException(status_code=413, detail="UPLOAD_TOO_LARGE")
                    digest.update(chunk)
                    stream.write(chunk)
            return store.enqueue(
                temporary, source_type=source_type,
                source_scope=source_scope, native_id=native_id,
                source_hash=digest.hexdigest(),
            )
        finally:
            temporary.unlink(missing_ok=True)

    @app.get("/api/v1/ingest/jobs/{job_id}", response_model=IngestionJob)
    def status(job_id: str) -> IngestionJob:
        """Return a job status or raise HTTP 404 for an unknown job."""
        job = store.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="JOB_NOT_FOUND")
        return job

    @app.post("/api/v1/ingest/jobs/{job_id}/retry", response_model=IngestionJob)
    def retry(job_id: str) -> IngestionJob:
        """Requeue a retryable job or report an unknown or ineligible job through HTTP."""
        job = store.retry(job_id)
        if job is None:
            if store.get(job_id) is None:
                raise HTTPException(status_code=404, detail="JOB_NOT_FOUND")
            raise HTTPException(status_code=409, detail="JOB_NOT_RETRYABLE")
        return job

    return app
