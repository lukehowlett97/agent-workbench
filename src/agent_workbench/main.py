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
from agent_workbench.workflows import (
    WORKFLOWS,
    build_task_prompt,
    validate_submission,
)

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
                "workflows": WORKFLOWS,
            },
        )

    @application.post("/jobs", include_in_schema=False)
    async def submit_job(
        username: Annotated[str, Depends(require_user)],
        prompt: Annotated[str, Form(min_length=1, max_length=20_000)],
        mode: Annotated[str, Form()] = "ask",
        workflow: Annotated[str, Form()] = "",
        files: Annotated[list[UploadFile] | None, File()] = None,
    ) -> RedirectResponse:
        """Create a validated mode-aware job and safely persist its uploads."""
        del username
        uploads = [upload for upload in (files or []) if upload.filename]
        try:
            validate_submission(mode, workflow, len(uploads))
            task_prompt = build_task_prompt(mode, workflow, prompt)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        job = repository.create(
            prompt.strip(),
            task_prompt=task_prompt,
            mode=mode,
            workflow=workflow,
        )
        workspace = runtime_settings.data_dir / "jobs" / job.id
        try:
            await store_uploads(
                uploads,
                workspace,
                runtime_settings.max_file_bytes,
                runtime_settings.max_job_bytes,
            )
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return RedirectResponse(url=f"/jobs/{job.id}", status_code=303)

    @application.get(
        "/jobs/{job_id}", response_class=HTMLResponse, include_in_schema=False
    )
    def job_detail(
        request: Request,
        job_id: str,
        username: Annotated[str, Depends(require_user)],
    ) -> HTMLResponse:
        """Render the current state and execution metadata."""
        del username
        job = repository.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        return templates.TemplateResponse(
            request=request,
            name="job.html",
            context={"job": job},
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
