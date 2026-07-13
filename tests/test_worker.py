"""Tests for atomic queue processing and failure handling."""

from __future__ import annotations

from pathlib import Path

from agent_workbench.executor import ExecutionResult, FixtureExecutor
from agent_workbench.jobs import Job, JobRepository
from agent_workbench.worker import Worker


def prepare_job(tmp_path: Path) -> tuple[JobRepository, Job]:
    """Create a repository, queued job and workspace."""
    repository = JobRepository(tmp_path / "workbench.sqlite3")
    repository.initialise()
    job = repository.create("Summarise the files")
    workspace = tmp_path / "jobs" / job.id
    (workspace / "input").mkdir(parents=True)
    (workspace / "output").mkdir()
    (workspace / "work").mkdir()
    (workspace / "input" / "sample.txt").write_text("hello", encoding="utf-8")
    return repository, job


def test_worker_completes_claimed_job(tmp_path: Path) -> None:
    """A successful executor should persist its result."""
    repository, job = prepare_job(tmp_path)
    worker = Worker(repository, FixtureExecutor(), tmp_path / "jobs")

    assert worker.run_once() is True

    completed = repository.get(job.id)
    assert completed is not None
    assert completed.status == "completed"
    assert "sample.txt" in (completed.result_markdown or "")
    assert (tmp_path / "jobs" / job.id / "output" / "report.md").exists()


def test_worker_records_safe_failure(tmp_path: Path) -> None:
    """Executor errors should fail the job without crashing the worker."""

    class BrokenExecutor:
        def execute(self, job: Job, workspace: Path) -> ExecutionResult:
            raise RuntimeError("provider unavailable")

    repository, job = prepare_job(tmp_path)
    worker = Worker(repository, BrokenExecutor(), tmp_path / "jobs")

    assert worker.run_once() is True
    failed = repository.get(job.id)
    assert failed is not None
    assert failed.status == "failed"
    assert failed.error_summary == "RuntimeError: provider unavailable"


def test_worker_returns_false_when_queue_is_empty(tmp_path: Path) -> None:
    """An idle worker should report that no work was claimed."""
    repository = JobRepository(tmp_path / "workbench.sqlite3")
    repository.initialise()

    assert Worker(repository, FixtureExecutor(), tmp_path / "jobs").run_once() is False
