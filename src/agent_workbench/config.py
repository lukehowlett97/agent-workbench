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
    max_file_bytes: int = 25 * 1024 * 1024
    max_job_bytes: int = 100 * 1024 * 1024

    @classmethod
    def from_env(cls) -> "Settings":
        """Load authentication, storage and environment settings."""
        return cls(
            username=os.getenv("WORKBENCH_USERNAME", ""),
            password=os.getenv("WORKBENCH_PASSWORD", ""),
            environment=os.getenv("WORKBENCH_ENVIRONMENT", "development"),
            data_dir=Path(os.getenv("WORKBENCH_DATA_DIR", "data")),
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
