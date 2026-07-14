"""Tests for persistent OpenClaw Gateway configuration."""

from pathlib import Path

import pytest

from agent_workbench.gateway import build_gateway_config, merge_config


def test_gateway_config_keeps_secrets_in_environment(tmp_path: Path) -> None:
    config = build_gateway_config(
        model="nvidia/test-model",
        workspace=tmp_path / "jobs",
        timeout_seconds=180,
    )

    gateway = config["gateway"]
    provider = config["models"]["providers"]["nvidia"]
    defaults = config["agents"]["defaults"]

    assert gateway == {
        "mode": "local",
        "bind": "lan",
        "auth": {"mode": "token"},
    }
    assert provider["apiKey"] == "${NVIDIA_API_KEY}"
    assert provider["models"][0]["id"] == "test-model"
    assert defaults["workspace"] == str(tmp_path / "jobs")
    assert defaults["model"]["primary"] == "nvidia/test-model"
    assert defaults["timeoutSeconds"] == 180


@pytest.mark.parametrize("model", ["", "test-model", "openai/test-model", "nvidia/"])
def test_gateway_config_rejects_unsupported_models(
    tmp_path: Path, model: str
) -> None:
    with pytest.raises(ValueError, match="nvidia/<model-id>"):
        build_gateway_config(
            model=model,
            workspace=tmp_path / "jobs",
            timeout_seconds=180,
        )


def test_managed_gateway_config_preserves_interactive_plugin_settings() -> None:
    config = merge_config(
        {
            "plugins": {"entries": {"parallel": {"enabled": True}}},
            "gateway": {"controlUi": {"allowedOrigins": ["http://localhost"]}},
        },
        {"gateway": {"mode": "local", "auth": {"mode": "token"}}},
    )

    assert config["plugins"] == {"entries": {"parallel": {"enabled": True}}}
    assert config["gateway"] == {
        "controlUi": {"allowedOrigins": ["http://localhost"]},
        "mode": "local",
        "auth": {"mode": "token"},
    }
