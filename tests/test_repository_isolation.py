"""Regression coverage for test database and checkout isolation."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPOSITORY = Path(__file__).parents[1]
PARENT = REPOSITORY.parents[1]


def porcelain(path: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(path), "status", "--porcelain=v1", "--untracked-files=all"],
        text=True,
    )


def runtime_artifacts() -> set[Path]:
    patterns = ("*.db", "*.sqlite", "*.sqlite3", "*.sqlite-wal", "*.sqlite-shm", ".coverage", "coverage.xml")
    return {
        path.relative_to(REPOSITORY)
        for pattern in patterns
        for path in REPOSITORY.rglob(pattern)
        if ".venv" not in path.parts and ".git" not in path.parts
    }


def test_database_tests_leave_both_checkouts_and_runtime_paths_unchanged() -> None:
    before_parent = porcelain(PARENT)
    before_nested = porcelain(REPOSITORY)
    before_artifacts = runtime_artifacts()
    environment = os.environ.copy()
    environment.pop("WORKBENCH_DATABASE_PATH", None)
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_jobs.py", "tests/test_workspaces.py", "-q"],
        cwd=REPOSITORY,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert porcelain(PARENT) == before_parent
    assert porcelain(REPOSITORY) == before_nested
    assert runtime_artifacts() == before_artifacts
