"""SQLite persistence for submitted analysis jobs."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class Job:
    """A queued analysis job."""

    id: str
    prompt: str
    status: str
    created_at: str


class JobRepository:
    """Create and query jobs using a small SQLite database."""

    def __init__(self, database: Path) -> None:
        self.database = database

    def connect(self) -> sqlite3.Connection:
        """Open a row-producing database connection."""
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        return connection

    def initialise(self) -> None:
        """Create the database directory and initial schema."""
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    prompt TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def create(self, prompt: str) -> Job:
        """Persist a new queued job."""
        job = Job(
            id=str(uuid.uuid4()),
            prompt=prompt,
            status="queued",
            created_at=datetime.now(UTC).isoformat(),
        )
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO jobs VALUES (?, ?, ?, ?)",
                (job.id, job.prompt, job.status, job.created_at),
            )
        return job

    def list_recent(self, limit: int = 50) -> list[Job]:
        """Return recent jobs in reverse chronological order."""
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [Job(**dict(row)) for row in rows]

    def get(self, job_id: str) -> Job | None:
        """Return one job when it exists."""
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        return Job(**dict(row)) if row else None
