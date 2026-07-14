"""Entrypoint for the long-lived OpenClaw Gateway container."""

from __future__ import annotations

import json
import os
from pathlib import Path


def build_gateway_config(
    *,
    model: str,
    workspace: Path,
    timeout_seconds: int,
) -> dict[str, object]:
    """Build the pinned Gateway configuration without embedding secrets."""
    provider, separator, model_id = model.partition("/")
    if provider != "nvidia" or not separator or not model_id:
        raise ValueError("Gateway models must use nvidia/<model-id>.")

    return {
        "gateway": {
            "mode": "local",
            "bind": "lan",
            "auth": {"mode": "token"},
        },
        "models": {
            "providers": {
                "nvidia": {
                    "baseUrl": "https://integrate.api.nvidia.com/v1",
                    "api": "openai-completions",
                    "apiKey": "${NVIDIA_API_KEY}",
                    "timeoutSeconds": timeout_seconds,
                    "models": [
                        {
                            "id": model_id,
                            "name": model_id,
                            "input": ["text"],
                            "contextWindow": 131_072,
                            "maxTokens": 8_192,
                        }
                    ],
                }
            }
        },
        "agents": {
            "defaults": {
                "workspace": str(workspace),
                "model": {"primary": model},
                "models": {"nvidia/*": {}},
                "timeoutSeconds": timeout_seconds,
                "memorySearch": {"enabled": False},
            }
        },
        "tools": {"profile": "coding"},
    }


def main() -> None:
    """Write config and replace this process with the OpenClaw Gateway."""
    if not os.getenv("NVIDIA_API_KEY", ""):
        raise SystemExit("NVIDIA_API_KEY is required by the Gateway.")
    if not os.getenv("OPENCLAW_GATEWAY_TOKEN", ""):
        raise SystemExit("OPENCLAW_GATEWAY_TOKEN is required by the Gateway.")

    state_dir = Path(os.getenv("OPENCLAW_STATE_DIR", "/state"))
    config_path = Path(
        os.getenv("OPENCLAW_CONFIG_PATH", str(state_dir / "openclaw.json"))
    )
    workspace = Path(os.getenv("OPENCLAW_GATEWAY_WORKSPACE", "/data/jobs"))
    model = os.getenv(
        "WORKBENCH_MODEL",
        "nvidia/nemotron-3-super-120b-a12b",
    )
    timeout_seconds = int(os.getenv("OPENCLAW_TIMEOUT_SECONDS", "300"))

    state_dir.mkdir(parents=True, exist_ok=True)
    workspace.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            build_gateway_config(
                model=model,
                workspace=workspace,
                timeout_seconds=timeout_seconds,
            ),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    os.environ["OPENCLAW_STATE_DIR"] = str(state_dir)
    os.environ["OPENCLAW_CONFIG_PATH"] = str(config_path)
    os.execvp("openclaw", ["openclaw", "gateway"])


if __name__ == "__main__":
    main()
