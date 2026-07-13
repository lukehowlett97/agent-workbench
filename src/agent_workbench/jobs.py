"""SQLite persistence and atomic state transitions for analysis jobs."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


@dataclass(frozen=True)
class Job:
    """A durable analysis job."""

    id: str
    prompt: str
    status: str
    created_at: str
    executor: str = "unknown"
    model: str = "unknown"
    started_at: str | None = None
    completed_at: str | None = None
    result_markdown: str | None = None
    error_summary: str | None = None


class JobRepository:
    """Create, claim and update jobs using SQLite transactions."""

    def __init__(self, database: Path) -> None:
        self.database = database

    def connect(self) -> sqlite3.Connection:
        """Open a row-producing database connection."""
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def initialise(self) -> None:
        """Create the database directory and schema."""
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    prompt TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    executor TEXT NOT NULL DEFAULT 'unknown',
                    model TEXT NOT NULL DEFAULT 'unknown',
                    started_at TEXT,
                    completed_at TEXT,
                    result_markdown TEXT,
                    error_summary TEXT
                )
                """
            )
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(jobs)").fetchall()
            }
            if "executor" not in columns:
                connection.execute(
                    "ALTER TABLE jobs ADD COLUMN executor TEXT NOT NULL "
                    "DEFAULT 'unknown'"
                )
            if "model" not in columns:
                connection.execute(
                    "ALTER TABLE jobs ADD COLUMN model TEXT NOT NULL DEFAULT 'unknown'"
                )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS jobs_status_created "
                "ON jobs(status, created_at)"
            )

    def create(self, prompt: str) -> Job:
        """Persist a new queued job."""
        job = Job(str(uuid.uuid4()), prompt, "queued", datetime.now(UTC).isoformat())
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO jobs(id, prompt, status, created_at) VALUES (?, ?, ?, ?)",
                (job.id, job.prompt, job.status, job.created_at),
            )
        return job

    def _from_row(self, row: sqlite3.Row | None) -> Job | None:
        return Job(**dict(row)) if row else None

    def get(self, job_id: str) -> Job | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
        return self._from_row(row)

    def list_recent(self, limit: int = 50) -> list[Job]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [Job(**dict(row)) for row in rows]

    def claim_next(self) -> Job | None:
        """Atomically claim the oldest queued job."""
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT id FROM jobs WHERE status = 'queued' "
                "ORDER BY created_at LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            started_at = datetime.now(UTC).isoformat()
            connection.execute(
                "UPDATE jobs SET status = 'running', started_at = ? "
                "WHERE id = ? AND status = 'queued'",
                (started_at, row["id"]),
            )
            claimed = connection.execute(
                "SELECT * FROM jobs WHERE id = ?", (row["id"],)
            ).fetchone()
        return self._from_row(claimed)

    def complete(
        self,
        job_id: str,
        result_markdown: str,
        executor: str,
        model: str,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE jobs SET status = 'completed', completed_at = ?, "
                "result_markdown = ?, executor = ?, model = ?, error_summary = NULL "
                "WHERE id = ? AND status = 'running'",
                (
                    datetime.now(UTC).isoformat(),
                    result_markdown,
                    executor,
                    model,
                    job_id,
                ),
            )

    def fail(self, job_id: str, summary: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE jobs SET status = 'failed', completed_at = ?, "
                "error_summary = ? WHERE id = ? AND status = 'running'",
                (datetime.now(UTC).isoformat(), summary[:1000], job_id),
            )

    def recover_stale(self, older_than: timedelta) -> int:
        cutoff = (datetime.now(UTC) - older_than).isoformat()
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE jobs SET status = 'queued', started_at = NULL "
                "WHERE status = 'running' AND started_at < ?",
                (cutoff,),
            )
        return cursor.rowcount
