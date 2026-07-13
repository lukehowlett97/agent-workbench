"""FastAPI entrypoint for Agent Workbench."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from agent_workbench.auth import require_user
from agent_workbench.config import Settings
from agent_workbench.jobs import JobRepository
from agent_workbench.storage import store_uploads

PACKAGE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the application with explicit runtime settings."""
    application = FastAPI(
        title="Agent Workbench",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
    )
    runtime_settings = settings or Settings.from_env()
    repository = JobRepository(runtime_settings.data_dir / "workbench.sqlite3")
    repository.initialise()
    application.state.settings = runtime_settings
    application.state.jobs = repository

    @application.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        """Return a non-sensitive liveness response."""
        return {"status": "ok"}

    @application.get("/", response_class=HTMLResponse, include_in_schema=False)
    def home(
        request: Request,
        username: Annotated[str, Depends(require_user)],
    ) -> HTMLResponse:
        """Render submission controls and recent jobs."""
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "username": username,
                "environment": runtime_settings.environment,
                "jobs": repository.list_recent(),
            },
        )

    @application.post("/jobs", include_in_schema=False)
    async def submit_job(
        username: Annotated[str, Depends(require_user)],
        prompt: Annotated[str, Form(min_length=1, max_length=20_000)],
        files: Annotated[list[UploadFile], File()],
    ) -> RedirectResponse:
        """Create a queued job and safely persist its uploads."""
        del username
        job = repository.create(prompt.strip())
        workspace = runtime_settings.data_dir / "jobs" / job.id
        try:
            await store_uploads(
                files,
                workspace,
                runtime_settings.max_file_bytes,
                runtime_settings.max_job_bytes,
            )
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return RedirectResponse(url=f"/jobs/{job.id}", status_code=303)

    @application.get("/jobs/{job_id}", include_in_schema=False)
    def job_detail(
        job_id: str,
        username: Annotated[str, Depends(require_user)],
    ) -> dict[str, str]:
        """Return the current state of one authenticated job."""
        del username
        job = repository.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        return {
            "id": job.id,
            "prompt": job.prompt,
            "status": job.status,
            "created_at": job.created_at,
        }

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
