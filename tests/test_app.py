"""Tests for the Stage 1 FastAPI application shell."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from agent_workbench.config import Settings
from agent_workbench.main import create_app


def make_client(
    username: str = "luke",
    password: str = "test-password",
) -> TestClient:
    """Create a test client with explicit credentials."""
    settings = Settings(
        username=username,
        password=password,
        environment="test",
    )
    return TestClient(create_app(settings))


def test_health_is_public_and_minimal() -> None:
    """The liveness endpoint must work without exposing configuration."""
    response = make_client().get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_home_requires_authentication() -> None:
    """The workbench must reject requests without credentials."""
    response = make_client().get("/")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == 'Basic realm="Agent Workbench"'


def test_home_rejects_invalid_credentials() -> None:
    """The workbench must reject an incorrect password."""
    response = make_client().get("/", auth=("luke", "incorrect"))

    assert response.status_code == 401


def test_home_renders_for_valid_credentials() -> None:
    """The workbench shell must render for the configured user."""
    response = make_client().get("/", auth=("luke", "test-password"))

    assert response.status_code == 200
    assert "Agent Workbench" in response.text
    assert "luke" in response.text
    assert "test" in response.text


def test_missing_server_credentials_fail_closed() -> None:
    """Missing environment credentials must not enable a default login."""
    client = TestClient(
        create_app(Settings(username="", password="", environment="test"))
    )

    response = client.get("/", auth=("admin", "admin"))

    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication is not configured."}


def test_job_result_displays_executor_and_model() -> None:
    client = make_client()
    job = client.app.state.jobs.create("Check the report")
    assert client.app.state.jobs.claim_next() is not None
    client.app.state.jobs.complete(
        job.id,
        "# Report\n\nDone.",
        "fixture",
        "fixture",
    )

    response = client.get(f"/jobs/{job.id}", auth=("luke", "test-password"))

    assert response.status_code == 200
    assert "Executor" in response.text
    assert "Model" in response.text
    assert "fixture" in response.text


def test_workspace_creation_and_follow_up_route(tmp_path: Path) -> None:
    client = TestClient(
        create_app(
            Settings(
                username="luke",
                password="test-password",
                environment="test",
                data_dir=tmp_path,
                max_file_bytes=100,
                max_job_bytes=100,
            )
        )
    )
    response = client.post(
        "/workspaces",
        auth=("luke", "test-password"),
        data={"title": "CSV review", "prompt": "Summarise the file"},
        files={"files": ("sample.csv", b"value\n1\n", "text/csv")},
        follow_redirects=False,
    )

    assert response.status_code == 303
    location = response.headers["location"]
    detail = client.get(location, auth=("luke", "test-password"))
    assert detail.status_code == 200
    assert "CSV review" in detail.text
    assert "Summarise the file" in detail.text

    follow_up = client.post(
        f"{location}/messages",
        auth=("luke", "test-password"),
        data={"content": "Now explain the trend"},
        follow_redirects=False,
    )
    assert follow_up.status_code == 409
    assert "running analysis" in follow_up.json()["detail"]
