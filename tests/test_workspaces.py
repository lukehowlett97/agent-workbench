"""Lifecycle and isolation tests for persistent workspaces."""
# ruff: noqa: E501

from __future__ import annotations

from pathlib import Path

from agent_workbench.workspaces import WorkspaceRepository


def make_repository(tmp_path: Path) -> WorkspaceRepository:
    repository = WorkspaceRepository(tmp_path / "workbench.sqlite3")
    repository.initialise()
    return repository


def test_workspace_creates_initial_message_and_run(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    workspace, message, run = repository.create_workspace(
        "Dataset", "Summarise the data", "fixture", "fixture"
    )

    assert workspace.status == "active"
    assert message.workspace_id == workspace.id
    assert message.role == "user"
    assert run.workspace_id == workspace.id
    assert run.trigger_message_id == message.id
    assert run.session_key == workspace.session_key
    assert run.status == "queued"


def test_follow_up_reuses_session_and_blocks_concurrent_run(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    workspace, _, first = repository.create_workspace(
        "Dataset", "First question", "fixture", "fixture"
    )
    claimed = repository.claim_next_run()
    assert claimed is not None
    assert claimed.id == first.id

    try:
        repository.add_follow_up(workspace.id, "Second question")
    except ValueError as exc:
        assert "running analysis" in str(exc)
    else:
        raise AssertionError("concurrent runs must be rejected")

    repository.complete_run(claimed, "First answer", "fixture", "fixture", 10)
    message, follow_up = repository.add_follow_up(workspace.id, "Second question")

    assert follow_up.trigger_message_id == message.id
    assert follow_up.session_key == workspace.session_key
    assert [item.role for item in repository.messages_for(workspace.id)] == [
        "user",
        "assistant",
        "user",
    ]


def test_workspaces_are_isolated_and_archived_workspaces_reject_messages(
    tmp_path: Path,
) -> None:
    repository = make_repository(tmp_path)
    first, _, _ = repository.create_workspace("One", "First", "fixture", "fixture")
    second, _, _ = repository.create_workspace("Two", "Second", "fixture", "fixture")

    assert [message.content for message in repository.messages_for(first.id)] == ["First"]
    assert [message.content for message in repository.messages_for(second.id)] == ["Second"]

    repository.archive(first.id)
    try:
        repository.add_follow_up(first.id, "Not allowed")
    except ValueError as exc:
        assert "Archived" in str(exc)
    else:
        raise AssertionError("archived workspaces must be immutable")


def test_legacy_jobs_are_migrated_without_removing_job_rows(tmp_path: Path) -> None:
    database = tmp_path / "workbench.sqlite3"
    import sqlite3

    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE jobs (id TEXT PRIMARY KEY, prompt TEXT, status TEXT, "
            "created_at TEXT, executor TEXT, model TEXT, started_at TEXT, "
            "completed_at TEXT, result_markdown TEXT, error_summary TEXT)"
        )
        connection.execute(
            "INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, NULL)",
            ("legacy-run", "Old prompt", "completed", "2026-01-01T00:00:00+00:00", "fixture", "fixture", "2026-01-01T00:01:00+00:00", "Old result"),
        )

    repository = make_repository(tmp_path)
    with repository.connect() as connection:
        assert connection.execute("SELECT count(*) FROM jobs").fetchone()[0] == 1
    workspace = repository.list_workspaces()[0]
    assert repository.runs_for(workspace.id)[0].id == "legacy-run"
    assert [message.content for message in repository.messages_for(workspace.id)] == [
        "Old prompt",
        "Old result",
    ]
