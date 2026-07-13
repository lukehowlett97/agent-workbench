"""Tests for persistent jobs and safe upload storage."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from agent_workbench.config import Settings
from agent_workbench.main import create_app


def make_client(data_dir: Path) -> TestClient:
    """Create an authenticated test application."""
    return TestClient(
        create_app(
            Settings(
                username="luke",
                password="secret",
                environment="test",
                data_dir=data_dir,
                max_file_bytes=100,
                max_job_bytes=150,
            )
        )
    )


def test_submit_job_persists_file_and_job(tmp_path: Path) -> None:
    """A valid upload should create a queued durable job."""
    client = make_client(tmp_path)

    response = client.post(
        "/jobs",
        auth=("luke", "secret"),
        data={"prompt": "Summarise this dataset"},
        files={"files": ("sample.csv", b"value\n1\n", "text/csv")},
        follow_redirects=False,
    )

    assert response.status_code == 303
    detail = client.get(response.headers["location"], auth=("luke", "secret"))
    assert detail.json()["status"] == "queued"
    stored = list((tmp_path / "jobs").glob("*/input/001-sample.csv"))
    assert len(stored) == 1
    assert stored[0].read_bytes() == b"value\n1\n"


def test_rejects_unsupported_file_type(tmp_path: Path) -> None:
    """Executable file extensions must be rejected."""
    response = make_client(tmp_path).post(
        "/jobs",
        auth=("luke", "secret"),
        data={"prompt": "Run this"},
        files={"files": ("payload.sh", b"exit 0", "text/plain")},
    )

    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_rejects_oversized_file(tmp_path: Path) -> None:
    """Files above the configured limit must be rejected."""
    response = make_client(tmp_path).post(
        "/jobs",
        auth=("luke", "secret"),
        data={"prompt": "Read this"},
        files={"files": ("large.txt", b"x" * 101, "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Upload size limit exceeded."
