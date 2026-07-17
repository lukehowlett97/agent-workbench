"""Persistent conversational workspace storage."""
# ruff: noqa: E501

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from mimetypes import guess_type
from pathlib import Path


def now() -> str:
    """Return a durable, timezone-aware timestamp."""
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class Workspace:
    id: str
    title: str
    status: str
    executor: str
    model: str
    session_key: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class Message:
    id: str
    workspace_id: str
    role: str
    content: str
    created_at: str
    run_id: str | None = None


@dataclass(frozen=True)
class Run:
    id: str
    workspace_id: str
    trigger_message_id: str
    prompt: str
    session_key: str
    status: str
    created_at: str
    executor: str = "unknown"
    model: str = "unknown"
    started_at: str | None = None
    completed_at: str | None = None
    error_summary: str | None = None
    duration_ms: int | None = None


@dataclass(frozen=True)
class Artefact:
    id: str
    workspace_id: str
    run_id: str | None
    kind: str
    original_name: str
    stored_name: str
    media_type: str
    size_bytes: int
    sha256: str
    created_at: str


class WorkspaceRepository:
    """SQLite repository for isolated, durable workspaces and runs."""

    def __init__(self, database: Path) -> None:
        self.database = database

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialise(self) -> None:
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS workspaces (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('active', 'archived')),
                    executor TEXT NOT NULL,
                    model TEXT NOT NULL,
                    session_key TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system-event')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    run_id TEXT
                );
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                    trigger_message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE RESTRICT,
                    status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
                    executor TEXT NOT NULL,
                    model TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    error_summary TEXT,
                    duration_ms INTEGER
                );
                CREATE TABLE IF NOT EXISTS artefacts (
                    id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                    run_id TEXT REFERENCES runs(id) ON DELETE SET NULL,
                    kind TEXT NOT NULL CHECK(kind IN ('input', 'output')),
                    original_name TEXT NOT NULL,
                    stored_name TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(workspace_id, kind, stored_name)
                );
                CREATE INDEX IF NOT EXISTS messages_workspace_created ON messages(workspace_id, created_at);
                CREATE INDEX IF NOT EXISTS runs_workspace_created ON runs(workspace_id, created_at);
                CREATE INDEX IF NOT EXISTS runs_status_created ON runs(status, created_at);
                CREATE INDEX IF NOT EXISTS artefacts_workspace_created ON artefacts(workspace_id, created_at);
                """
            )
            self._migrate_legacy_jobs(connection)

    def _migrate_legacy_jobs(self, connection: sqlite3.Connection) -> None:
        """Mirror old one-shot jobs into immutable workspace history once."""
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'jobs'"
        ).fetchone()
        if exists is None:
            return
        rows = connection.execute("SELECT * FROM jobs ORDER BY created_at").fetchall()
        for job in rows:
            run_exists = connection.execute(
                "SELECT 1 FROM runs WHERE id = ?", (job["id"],)
            ).fetchone()
            if run_exists:
                continue
            workspace_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"legacy-workspace:{job['id']}"))
            session_key = f"agent:main:workspace:{workspace_id}"
            title = job["prompt"].strip().splitlines()[0][:80] or "Imported job"
            connection.execute(
                "INSERT OR IGNORE INTO workspaces VALUES (?, ?, 'active', ?, ?, ?, ?, ?)",
                (workspace_id, title, job["executor"], job["model"], session_key, job["created_at"], job["created_at"]),
            )
            message_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"legacy-message:{job['id']}"))
            connection.execute(
                "INSERT OR IGNORE INTO messages VALUES (?, ?, 'user', ?, ?, NULL)",
                (message_id, workspace_id, job["prompt"], job["created_at"]),
            )
            connection.execute(
                "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    job["id"], workspace_id, message_id, job["status"], job["executor"], job["model"],
                    job["created_at"], job["started_at"], job["completed_at"], job["error_summary"], None,
                ),
            )
            if job["result_markdown"]:
                connection.execute(
                    "INSERT INTO messages VALUES (?, ?, 'assistant', ?, ?, ?)",
                    (str(uuid.uuid4()), workspace_id, job["result_markdown"], job["completed_at"] or job["created_at"], job["id"]),
                )

    @staticmethod
    def _workspace(row: sqlite3.Row | None) -> Workspace | None:
        return Workspace(**dict(row)) if row else None

    @staticmethod
    def _message(row: sqlite3.Row | None) -> Message | None:
        return Message(**dict(row)) if row else None

    @staticmethod
    def _run(row: sqlite3.Row | None) -> Run | None:
        return Run(**dict(row)) if row else None

    def create_workspace(self, title: str, prompt: str, executor: str, model: str) -> tuple[Workspace, Message, Run]:
        workspace = Workspace(str(uuid.uuid4()), title.strip()[:120] or "Untitled workspace", "active", executor, model, f"agent:main:workspace:{uuid.uuid4()}", now(), now())
        message = Message(str(uuid.uuid4()), workspace.id, "user", prompt.strip(), now())
        run = Run(str(uuid.uuid4()), workspace.id, message.id, message.content, workspace.session_key, "queued", now(), executor, model)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("INSERT INTO workspaces VALUES (?, ?, ?, ?, ?, ?, ?, ?)", tuple(workspace.__dict__.values()))
            connection.execute("INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?)", tuple(message.__dict__.values()))
            connection.execute("INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (run.id, run.workspace_id, run.trigger_message_id, run.status, run.executor, run.model, run.created_at, run.started_at, run.completed_at, run.error_summary, run.duration_ms))
        return workspace, message, run

    def get_workspace(self, workspace_id: str) -> Workspace | None:
        with self.connect() as connection:
            return self._workspace(connection.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,)).fetchone())

    def list_workspaces(self, include_archived: bool = False) -> list[Workspace]:
        query = "SELECT * FROM workspaces" + ("" if include_archived else " WHERE status = 'active'") + " ORDER BY updated_at DESC"
        with self.connect() as connection:
            return [Workspace(**dict(row)) for row in connection.execute(query).fetchall()]

    def messages_for(self, workspace_id: str) -> list[Message]:
        with self.connect() as connection:
            return [Message(**dict(row)) for row in connection.execute("SELECT * FROM messages WHERE workspace_id = ? ORDER BY created_at", (workspace_id,)).fetchall()]

    def runs_for(self, workspace_id: str) -> list[Run]:
        with self.connect() as connection:
            rows = connection.execute("SELECT r.*, m.content AS prompt, w.session_key FROM runs r JOIN messages m ON m.id = r.trigger_message_id JOIN workspaces w ON w.id = r.workspace_id WHERE r.workspace_id = ? ORDER BY r.created_at", (workspace_id,)).fetchall()
        return [Run(**dict(row)) for row in rows]

    def artefacts_for(self, workspace_id: str) -> list[Artefact]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM artefacts WHERE workspace_id = ? ORDER BY created_at",
                (workspace_id,),
            ).fetchall()
        return [Artefact(**dict(row)) for row in rows]

    def record_artefacts(self, workspace_id: str, artefacts: Iterable[Artefact]) -> None:
        with self.connect() as connection:
            connection.executemany(
                "INSERT OR IGNORE INTO artefacts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [tuple(artefact.__dict__.values()) for artefact in artefacts],
            )

    def inventory_output(self, workspace_id: str, run_id: str, output_dir: Path) -> None:
        """Record regular output files without following links outside the workspace."""
        if not output_dir.is_dir():
            return
        artefacts: list[Artefact] = []
        for path in output_dir.rglob("*"):
            if path.is_symlink() or not path.is_file():
                continue
            stored_name = str(path.relative_to(output_dir))
            digest = sha256(path.read_bytes()).hexdigest()
            artefacts.append(
                Artefact(
                    str(uuid.uuid4()),
                    workspace_id,
                    run_id,
                    "output",
                    path.name,
                    stored_name,
                    guess_type(path.name)[0] or "application/octet-stream",
                    path.stat().st_size,
                    digest,
                    now(),
                )
            )
        self.record_artefacts(workspace_id, artefacts)

    def add_follow_up(self, workspace_id: str, content: str) -> tuple[Message, Run]:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            workspace = connection.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
            if workspace is None:
                raise KeyError("Workspace not found.")
            if workspace["status"] != "active":
                raise ValueError("Archived workspaces cannot accept follow-ups.")
            busy = connection.execute("SELECT 1 FROM runs WHERE workspace_id = ? AND status IN ('queued', 'running')", (workspace_id,)).fetchone()
            if busy:
                raise ValueError("This workspace already has a running analysis.")
            message = Message(str(uuid.uuid4()), workspace_id, "user", content.strip(), now())
            run = Run(str(uuid.uuid4()), workspace_id, message.id, message.content, workspace["session_key"], "queued", now(), workspace["executor"], workspace["model"])
            connection.execute("INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?)", tuple(message.__dict__.values()))
            connection.execute("INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (run.id, run.workspace_id, run.trigger_message_id, run.status, run.executor, run.model, run.created_at, None, None, None, None))
            connection.execute("UPDATE workspaces SET updated_at = ? WHERE id = ?", (now(), workspace_id))
        return message, run

    def claim_next_run(self) -> Run | None:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT r.id FROM runs r WHERE r.status = 'queued' AND NOT EXISTS (SELECT 1 FROM runs active WHERE active.workspace_id = r.workspace_id AND active.status = 'running') ORDER BY r.created_at LIMIT 1").fetchone()
            if row is None:
                return None
            started = now()
            connection.execute("UPDATE runs SET status = 'running', started_at = ? WHERE id = ? AND status = 'queued'", (started, row["id"]))
            claimed = connection.execute("SELECT r.*, m.content AS prompt, w.session_key FROM runs r JOIN messages m ON m.id = r.trigger_message_id JOIN workspaces w ON w.id = r.workspace_id WHERE r.id = ?", (row["id"],)).fetchone()
        return self._run(claimed)

    def complete_run(self, run: Run, markdown: str, executor: str, model: str, duration_ms: int) -> None:
        finished = now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("UPDATE runs SET status = 'completed', completed_at = ?, executor = ?, model = ?, duration_ms = ?, error_summary = NULL WHERE id = ? AND status = 'running'", (finished, executor, model, duration_ms, run.id))
            connection.execute("INSERT INTO messages VALUES (?, ?, 'assistant', ?, ?, ?)", (str(uuid.uuid4()), run.workspace_id, markdown, finished, run.id))
            connection.execute("UPDATE workspaces SET updated_at = ?, executor = ?, model = ? WHERE id = ?", (finished, executor, model, run.workspace_id))

    def fail_run(self, run: Run, summary: str, duration_ms: int) -> None:
        finished = now()
        with self.connect() as connection:
            connection.execute("UPDATE runs SET status = 'failed', completed_at = ?, error_summary = ?, duration_ms = ? WHERE id = ? AND status = 'running'", (finished, summary[:1000], duration_ms, run.id))
            connection.execute("UPDATE workspaces SET updated_at = ? WHERE id = ?", (finished, run.workspace_id))

    def rename(self, workspace_id: str, title: str) -> None:
        with self.connect() as connection:
            connection.execute("UPDATE workspaces SET title = ?, updated_at = ? WHERE id = ?", (title.strip()[:120] or "Untitled workspace", now(), workspace_id))

    def archive(self, workspace_id: str) -> None:
        with self.connect() as connection:
            connection.execute("UPDATE workspaces SET status = 'archived', updated_at = ? WHERE id = ?", (now(), workspace_id))

    def recover_stale(self, older_than: timedelta) -> int:
        cutoff = (datetime.now(UTC) - older_than).isoformat()
        with self.connect() as connection:
            cursor = connection.execute("UPDATE runs SET status = 'queued', started_at = NULL WHERE status = 'running' AND started_at < ?", (cutoff,))
        return cursor.rowcount
