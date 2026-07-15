"""Entrypoint for the long-lived OpenClaw Gateway container."""

from __future__ import annotations

import json
import os
from pathlib import Path


def merge_config(existing: dict[str, object], managed: dict[str, object]) -> dict[str, object]:
    """Preserve interactive settings while enforcing managed runtime settings."""
    merged = existing.copy()
    for key, value in managed.items():
        previous = merged.get(key)
        if isinstance(previous, dict) and isinstance(value, dict):
            merged[key] = merge_config(previous, value)
        else:
            merged[key] = value
    return merged


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

    builder_tools = ["workspace_list", "workspace_read", "workspace_write", "workspace_apply_patch", "git_create_branch", "git_diff", "git_commit", "run_build", "run_tests", "create_preview", "deploy_preview", "verify_preview"]
    unsafe_tools = ["exec", "process", "shell", "ssh", "read", "write", "edit", "apply_patch", "browser", "web_fetch", "web_search"]
    builder_non_plugin_tools = unsafe_tools + ["get_goal", "create_goal", "update_goal", "skill_workshop", "update_plan", "sessions_list", "sessions_history", "sessions_send", "sessions_spawn", "sessions_yield", "subagents", "session_status"]
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
            },
            "list": [
                {"id": "main", "default": True, "tools": {"deny": builder_tools}},
                {"id": "career", "tools": {"deny": builder_tools}},
                {"id": "builder-agent", "workspace": str(workspace), "tools": {"alsoAllow": builder_tools, "deny": builder_non_plugin_tools}},
            ],
        },
        "tools": {"profile": "coding", "deny": unsafe_tools},
    }


def load_existing_config(config_path: Path) -> dict[str, object]:
    """Return a user-maintained OpenClaw config, ignoring incomplete first-run files."""
    if not config_path.is_file():
        return {}
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return config if isinstance(config, dict) else {}


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
    timeout_seconds = int(os.getenv("OPENCLAW_GATEWAY_TIMEOUT_SECONDS", "300"))

    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "home").mkdir(parents=True, exist_ok=True)
    (state_dir / "npm-cache").mkdir(parents=True, exist_ok=True)
    workspace.mkdir(parents=True, exist_ok=True)
    config = merge_config(
        load_existing_config(config_path),
        build_gateway_config(
            model=model,
            workspace=workspace,
            timeout_seconds=timeout_seconds,
        ),
    )
    config_path.write_text(
        json.dumps(config, indent=2) + "\n",
        encoding="utf-8",
    )

    os.environ["OPENCLAW_STATE_DIR"] = str(state_dir)
    os.environ["OPENCLAW_CONFIG_PATH"] = str(config_path)
    os.execvp("openclaw", ["openclaw", "gateway"])


if __name__ == "__main__":
    main()
