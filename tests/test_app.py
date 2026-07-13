"""Tests for the Stage 1 FastAPI application shell."""

from __future__ import annotations

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
