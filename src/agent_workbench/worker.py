"""Queue worker orchestration independent of the agent implementation."""

from __future__ import annotations

import argparse
import time
from datetime import timedelta
from pathlib import Path

from agent_workbench.config import Settings
from agent_workbench.executor import Executor, FixtureExecutor
from agent_workbench.jobs import JobRepository


class Worker:
    """Claim and execute durable jobs one at a time."""

    def __init__(
        self,
        repository: JobRepository,
        executor: Executor,
        jobs_dir: Path,
    ) -> None:
        self.repository = repository
        self.executor = executor
        self.jobs_dir = jobs_dir

    def run_once(self) -> bool:
        """Process one job and return whether work was claimed."""
        job = self.repository.claim_next()
        if job is None:
            return False

        try:
            result = self.executor.execute(job, self.jobs_dir / job.id)
        except Exception as exc:
            # Store only the exception class and bounded message; never a traceback.
            self.repository.fail(job.id, f"{type(exc).__name__}: {exc}")
        else:
            self.repository.complete(job.id, result.markdown)
        return True


def main() -> int:
    """Run the development worker once or continuously."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args()

    settings = Settings.from_env()
    repository = JobRepository(settings.data_dir / "workbench.sqlite3")
    repository.initialise()
    repository.recover_stale(timedelta(minutes=15))
    worker = Worker(repository, FixtureExecutor(), settings.data_dir / "jobs")

    if args.once:
        worker.run_once()
        return 0

    while True:
        if not worker.run_once():
            time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
