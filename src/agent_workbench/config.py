"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Runtime settings without retaining unrelated environment values."""

    username: str
    password: str
    environment: str = "development"

    @classmethod
    def from_env(cls) -> "Settings":
        """Load authentication and environment settings.

        Returns:
            Settings populated from process environment variables.
        """
        return cls(
            username=os.getenv("WORKBENCH_USERNAME", ""),
            password=os.getenv("WORKBENCH_PASSWORD", ""),
            environment=os.getenv("WORKBENCH_ENVIRONMENT", "development"),
        )

    @property
    def authentication_configured(self) -> bool:
        """Return whether both required credentials are present."""
        return bool(self.username and self.password)
