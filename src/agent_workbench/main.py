"""FastAPI entrypoint for Agent Workbench."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from agent_workbench.auth import require_user
from agent_workbench.config import Settings

PACKAGE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the application with explicit runtime settings.

    Args:
        settings: Optional settings override, primarily for tests.

    Returns:
        Configured FastAPI application.
    """
    application = FastAPI(
        title="Agent Workbench",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
    )
    application.state.settings = settings or Settings.from_env()

    @application.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        """Return a non-sensitive liveness response."""
        return {"status": "ok"}

    @application.get("/", response_class=HTMLResponse, include_in_schema=False)
    def home(
        request: Request,
        username: Annotated[str, Depends(require_user)],
    ) -> HTMLResponse:
        """Render the authenticated Stage 1 landing page."""
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "username": username,
                "environment": application.state.settings.environment,
            },
        )

    return application


app = create_app()


def run() -> None:
    """Run the development server."""
    uvicorn.run(
        "agent_workbench.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )
