"""Authentication dependencies for private workbench routes."""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from agent_workbench.config import Settings

basic_auth = HTTPBasic(auto_error=False)


def require_user(
    request: Request,
    credentials: Annotated[HTTPBasicCredentials | None, Depends(basic_auth)],
) -> str:
    """Validate the configured single-user HTTP Basic credentials.

    Args:
        request: Current request containing application settings.
        credentials: Credentials supplied by the browser.

    Returns:
        Authenticated username.

    Raises:
        HTTPException: If authentication is unavailable or invalid.
    """
    settings: Settings = request.app.state.settings

    if not settings.authentication_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured.",
        )

    username_ok = credentials is not None and secrets.compare_digest(
        credentials.username.encode(),
        settings.username.encode(),
    )
    password_ok = credentials is not None and secrets.compare_digest(
        credentials.password.encode(),
        settings.password.encode(),
    )

    if not username_ok or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
            headers={"WWW-Authenticate": 'Basic realm="Agent Workbench"'},
        )

    return settings.username
