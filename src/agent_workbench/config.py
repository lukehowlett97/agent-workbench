"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Runtime settings without retaining unrelated environment values."""

    username: str
    password: str
    environment: str = "development"
    data_dir: Path = Path("data")
    executor: str = "fixture"
    model: str = "nvidia/nemotron-3-super-120b-a12b"
    nvidia_api_key: str = ""
    openclaw_version: str = "2026.6.11"
    openclaw_gateway_url: str = "ws://gateway:18789"
    openclaw_gateway_token: str = ""
    openclaw_timeout_seconds: int = 300
    max_file_bytes: int = 25 * 1024 * 1024
    max_job_bytes: int = 100 * 1024 * 1024

    @classmethod
    def from_env(cls) -> Settings:
        """Load authentication, storage and executor settings."""
        return cls(
            username=os.getenv("WORKBENCH_USERNAME", ""),
            password=os.getenv("WORKBENCH_PASSWORD", ""),
            environment=os.getenv("WORKBENCH_ENVIRONMENT", "development"),
            data_dir=Path(os.getenv("WORKBENCH_DATA_DIR", "data")),
            executor=os.getenv("WORKBENCH_EXECUTOR", "fixture"),
            model=os.getenv(
                "WORKBENCH_MODEL", "nvidia/nemotron-3-super-120b-a12b"
            ),
            nvidia_api_key=os.getenv("NVIDIA_API_KEY", ""),
            openclaw_version=os.getenv("OPENCLAW_VERSION", "2026.7.1"),
            openclaw_gateway_url=os.getenv(
                "OPENCLAW_GATEWAY_URL", "ws://gateway:18789"
            ),
            openclaw_gateway_token=os.getenv("OPENCLAW_GATEWAY_TOKEN", ""),
            openclaw_timeout_seconds=int(
                os.getenv(
                    "OPENCLAW_GATEWAY_TIMEOUT_SECONDS",
                    os.getenv("OPENCLAW_TIMEOUT_SECONDS", "300"),
                )
            ),
            max_file_bytes=int(
                os.getenv("WORKBENCH_MAX_FILE_BYTES", str(25 * 1024 * 1024))
            ),
            max_job_bytes=int(
                os.getenv("WORKBENCH_MAX_JOB_BYTES", str(100 * 1024 * 1024))
            ),
        )

    @property
    def authentication_configured(self) -> bool:
        """Return whether both required credentials are present."""
        return bool(self.username and self.password)
