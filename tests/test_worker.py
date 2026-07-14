"""Tests for atomic queue processing and failure handling."""

from __future__ import annotations

import subprocess
from pathlib import Path

from agent_workbench.config import Settings
from agent_workbench.executor import ExecutionResult, FixtureExecutor, OpenClawExecutor
from agent_workbench.jobs import Job, JobRepository
from agent_workbench.worker import Worker, build_executor


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
    assert completed.executor == "fixture"
    assert completed.model == "fixture"
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


def test_worker_executor_selection_is_explicit() -> None:
    assert isinstance(
        build_executor(Settings(username="", password="", executor="fixture")),
        FixtureExecutor,
    )
    assert isinstance(
        build_executor(
            Settings(
                username="",
                password="",
                executor="openclaw",
                nvidia_api_key="test-key",
            )
        ),
        OpenClawExecutor,
    )


def test_worker_rejects_unknown_executor() -> None:
    try:
        build_executor(Settings(username="", password="", executor="unknown"))
    except ValueError as exc:
        assert "WORKBENCH_EXECUTOR" in str(exc)
    else:
        raise AssertionError("unknown executor should be rejected")


def test_openclaw_executor_passes_api_key_only_to_subprocess(
    tmp_path: Path, monkeypatch
) -> None:
    repository, job = prepare_job(tmp_path)
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["env"] = kwargs["env"]
        config = Path(kwargs["env"]["OPENCLAW_CONFIG_PATH"])
        captured["config"] = config.read_text(encoding="utf-8")
        report = tmp_path / "jobs" / job.id / "output" / "report.md"
        report.write_text("# OpenClaw report", encoding="utf-8")

        class Completed:
            stdout = ""

        return Completed()

    monkeypatch.setattr("agent_workbench.executor.subprocess.run", fake_run)
    result = OpenClawExecutor("secret-key", "nvidia/test-model").execute(
        job, tmp_path / "jobs" / job.id
    )

    assert result.executor == "openclaw"
    assert result.model == "nvidia/test-model"
    assert captured["env"]["NVIDIA_API_KEY"] == "secret-key"
    assert "--message" in captured["command"]
    assert f"agent:main:workbench:{job.id}" in captured["command"]
    assert any("Respond helpfully and directly" in part for part in captured["command"])
    assert '"id": "test-model"' in captured["config"]
    assert '"maxTokens": 8192' in captured["config"]
    workspace = tmp_path / "jobs" / job.id
    assert f'"workspace": "{workspace}"' in captured["config"]


def test_openclaw_executor_redacts_key_in_process_errors(
    tmp_path: Path, monkeypatch
) -> None:
    repository, job = prepare_job(tmp_path)

    def fake_run(*_args, **_kwargs):
        raise subprocess.CalledProcessError(
            1, "openclaw", stderr="authentication failed for secret-key"
        )

    monkeypatch.setattr("agent_workbench.executor.subprocess.run", fake_run)

    try:
        OpenClawExecutor("secret-key", "nvidia/test-model").execute(
            job, tmp_path / "jobs" / job.id
        )
    except RuntimeError as exc:
        assert "OpenClaw exited 1" in str(exc)
        assert "[redacted]" in str(exc)
        assert "secret-key" not in str(exc)
    else:
        raise AssertionError("OpenClaw error should be reported")
