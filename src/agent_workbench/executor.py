"""Execution boundary between the queue and OpenClaw."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from agent_workbench.jobs import Job


@dataclass(frozen=True)
class ExecutionResult:
    """Successful executor output."""

    markdown: str


class Executor(Protocol):
    """Interface implemented by real and test agent executors."""

    def execute(self, job: Job, workspace: Path) -> ExecutionResult:
        """Execute one job inside its assigned workspace."""
        ...


class FixtureExecutor:
    """Deterministic executor for development and automated tests."""

    def execute(self, job: Job, workspace: Path) -> ExecutionResult:
        """Create a safe report without contacting a model."""
        files = sorted(path.name for path in (workspace / "input").iterdir())
        markdown = (
            f"# Analysis job {job.id}\n\n"
            f"Prompt: {job.prompt}\n\n"
            "## Input files\n\n"
            + "\n".join(f"- {name}" for name in files)
            + "\n"
        )
        output = workspace / "output" / "report.md"
        output.write_text(markdown, encoding="utf-8")
        return ExecutionResult(markdown=markdown)
