"""Entrypoint for the long-lived OpenClaw Gateway container."""

from __future__ import annotations

import json
import os
import shutil
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
    maintenance_service_secret: str | None = None,
    builder_service_secret: str | None = None,
    google_account: str | None = None,
    gog_keyring_password: str | None = None,
) -> dict[str, object]:
    """Build the pinned Gateway configuration with an optional runtime secret."""
    provider, separator, model_id = model.partition("/")
    if provider != "nvidia" or not separator or not model_id:
        raise ValueError("Gateway models must use nvidia/<model-id>.")

    builder_tools = ["site_publish", "site_status", "site_read", "site_rollback"]
    builder_low_level_tools = ["workspace_list", "workspace_read", "workspace_write", "workspace_apply_patch", "git_create_branch", "git_diff", "git_commit", "run_build", "run_tests", "create_preview", "deploy_preview", "verify_preview"]
    maintenance_tools = ["maintenance_status", "maintenance_capabilities", "maintenance_plan", "maintenance_execute", "maintenance_apply", "maintenance_job_status", "maintenance_rollback"]
    capability_tools = ["capability_catalog", "capability_run", "capability_install", "capability_create", "capability_update", "capability_remove", "capability_status", "capability_rollback", "capability_set_mode"]
    google_workspace_tools = [
        "calendar_events",
        "gmail_get_message",
        "gmail_get_thread",
        "gmail_search",
    ]
    resolved_maintenance_secret = (
        maintenance_service_secret
        if maintenance_service_secret is not None
        else "${MAINTENANCE_SERVICE_SECRET}"
    )
    resolved_builder_secret = (
        builder_service_secret
        if builder_service_secret is not None
        else "${BUILDER_SERVICE_SECRET}"
    )
    unsafe_tools = ["exec", "process", "shell", "ssh", "read", "write", "edit", "apply_patch", "browser", "web_fetch", "web_search"]
    builder_non_plugin_tools = unsafe_tools + ["get_goal", "create_goal", "update_goal", "skill_workshop", "update_plan", "sessions_list", "sessions_history", "sessions_send", "sessions_spawn", "sessions_yield", "subagents", "session_status"]
    config: dict[str, object] = {
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
                {"id": "main", "default": True, "tools": {"alsoAllow": ["capability_catalog", "capability_run"], "deny": builder_tools + builder_low_level_tools + maintenance_tools + capability_tools[2:]}},
                {"id": "career", "tools": {"alsoAllow": ["capability_catalog", "capability_run"], "deny": builder_tools + builder_low_level_tools + maintenance_tools + capability_tools[2:]}},
                {"id": "builder-agent", "workspace": str(workspace), "tools": {"alsoAllow": builder_tools + ["capability_catalog", "capability_run"], "deny": builder_non_plugin_tools + builder_low_level_tools + maintenance_tools + capability_tools[2:] + google_workspace_tools}},
                {"id": "maintenance-agent", "workspace": str(workspace / "maintenance"), "agentDir": "/state/agents/maintenance-agent/agent", "tools": {"alsoAllow": maintenance_tools, "deny": builder_non_plugin_tools + builder_tools + builder_low_level_tools + google_workspace_tools}},
                {"id": "capability-agent", "workspace": str(workspace / "capability"), "agentDir": "/state/agents/capability-agent/agent", "tools": {"alsoAllow": capability_tools, "deny": builder_non_plugin_tools + builder_tools + builder_low_level_tools + maintenance_tools}},
            ],
        },
        "tools": {"profile": "coding", "deny": unsafe_tools},
        "skills": {
            "load": {"extraDirs": ["/opt/openclaw-builder-skill", "/opt/openclaw-maintenance-skill", "/opt/openclaw-capability-skill"]},
            "entries": {"gog": {"enabled": False}},
        },
        "plugins": {
            "entries": {
                "openclaw-builder-tools": {"enabled": True, "config": {"serviceSecret": resolved_builder_secret}},
                "openclaw-maintenance-tools": {"enabled": True, "config": {"serviceSecret": resolved_maintenance_secret}},
                "openclaw-capability-tools": {"enabled": True, "config": {"runtimeUrl": "http://capability-runtime:8090", "serviceSecret": resolved_maintenance_secret}},
                "openclaw-capability-ui": {"enabled": True, "config": {"serviceSecret": resolved_maintenance_secret}},
            },
            "load": {"paths": ["/opt/openclaw-builder-tools", "/opt/openclaw-maintenance-tools", "/opt/openclaw-capability-tools", "/opt/openclaw-capability-ui"]},
            "allow": ["openclaw-builder-tools", "openclaw-maintenance-tools", "openclaw-capability-tools", "openclaw-capability-ui"],
        },
    }
    if google_account and gog_keyring_password:
        config["mcp"] = {
            "servers": {
                "google-workspace": {
                    "command": "/usr/local/bin/gog",
                    "args": [
                        "--account",
                        "${GOG_ACCOUNT}",
                        "--readonly",
                        "--gmail-no-send",
                        "mcp",
                        "--allow-tool",
                        "gmail,calendar",
                    ],
                    "toolFilter": {"include": google_workspace_tools},
                }
            }
        }
    return config


def load_existing_config(config_path: Path) -> dict[str, object]:
    """Return a user-maintained OpenClaw config, ignoring incomplete first-run files."""
    if not config_path.is_file():
        return {}
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return config if isinstance(config, dict) else {}


def provision_maintenance_agent(state_dir: Path) -> None:
    """Seed the isolated maintenance agent directory without overwriting state."""
    source = Path("/app/agent-assets/maintenance-agent")
    target = state_dir / "agents" / "maintenance-agent" / "agent"
    if not source.is_dir():
        raise SystemExit("maintenance agent assets are missing from the Gateway image")
    target.mkdir(parents=True, exist_ok=True)
    for item in source.rglob("*"):
        if not item.is_file():
            continue
        destination = target / item.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copyfile(item, destination)


def provision_capability_agent(state_dir: Path) -> None:
    """Seed the isolated capability agent directory without overwriting state."""
    source = Path("/app/agent-assets/capability-agent")
    target = state_dir / "agents" / "capability-agent" / "agent"
    if not source.is_dir():
        raise SystemExit("capability agent assets are missing from the Gateway image")
    target.mkdir(parents=True, exist_ok=True)
    for item in source.rglob("*"):
        if not item.is_file() or "skills" in item.relative_to(source).parts:
            continue
        destination = target / item.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copyfile(item, destination)


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
    maintenance_service_secret = os.getenv("MAINTENANCE_SERVICE_SECRET", "")
    if len(maintenance_service_secret) < 32:
        raise SystemExit("MAINTENANCE_SERVICE_SECRET is required by the Gateway.")

    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "home").mkdir(parents=True, exist_ok=True)
    (state_dir / "npm-cache").mkdir(parents=True, exist_ok=True)
    provision_maintenance_agent(state_dir)
    provision_capability_agent(state_dir)
    workspace.mkdir(parents=True, exist_ok=True)
    config = merge_config(
        load_existing_config(config_path),
        build_gateway_config(
            model=model,
            workspace=workspace,
            timeout_seconds=timeout_seconds,
            maintenance_service_secret=maintenance_service_secret,
            builder_service_secret=os.getenv("BUILDER_SERVICE_SECRET", ""),
            google_account=os.getenv("GOG_ACCOUNT", ""),
            gog_keyring_password=os.getenv("GOG_KEYRING_PASSWORD", ""),
        ),
    )
    config_path.write_text(
        json.dumps(config, indent=2) + "\n",
        encoding="utf-8",
    )
    config_path.chmod(0o600)

    os.environ["OPENCLAW_STATE_DIR"] = str(state_dir)
    os.environ["OPENCLAW_CONFIG_PATH"] = str(config_path)
    os.execvp("openclaw", ["openclaw", "gateway"])


if __name__ == "__main__":
    main()
