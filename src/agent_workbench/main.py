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
from agent_workbench.workspaces import WorkspaceRepository

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
    workspaces = WorkspaceRepository(runtime_settings.data_dir / "workbench.sqlite3")
    workspaces.initialise()
    application.state.settings = runtime_settings
    application.state.jobs = repository
    application.state.workspaces = workspaces

    @application.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        """Return a non-sensitive liveness response."""
        return {"status": "ok"}

    @application.get("/", response_class=HTMLResponse, include_in_schema=False)
    def home(
        request: Request,
        username: Annotated[str, Depends(require_user)],
    ) -> HTMLResponse:
        """Render persistent workspaces and new-workspace controls."""
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "username": username,
                "environment": runtime_settings.environment,
                "workspaces": workspaces.list_workspaces(),
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

    @application.post("/workspaces", include_in_schema=False)
    async def create_workspace(
        username: Annotated[str, Depends(require_user)],
        prompt: Annotated[str, Form(min_length=1, max_length=20_000)],
        files: Annotated[list[UploadFile], File()],
        title: Annotated[str, Form(max_length=120)] = "",
    ) -> RedirectResponse:
        """Create a workspace, its first message, and queued first run."""
        del username
        workspace, _, _ = workspaces.create_workspace(
            title or prompt.strip().splitlines()[0],
            prompt,
            runtime_settings.executor,
            runtime_settings.model,
        )
        try:
            await store_uploads(
                files,
                runtime_settings.data_dir / "workspaces" / workspace.id,
                runtime_settings.max_file_bytes,
                runtime_settings.max_job_bytes,
            )
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse(url=f"/workspaces/{workspace.id}", status_code=303)

    @application.get(
        "/workspaces/{workspace_id}",
        response_class=HTMLResponse,
        include_in_schema=False,
    )
    def workspace_detail(
        request: Request,
        workspace_id: str,
        username: Annotated[str, Depends(require_user)],
    ) -> HTMLResponse:
        """Render conversation and run history for one isolated workspace."""
        del username
        workspace = workspaces.get_workspace(workspace_id)
        if workspace is None:
            raise HTTPException(status_code=404, detail="Workspace not found.")
        runs = workspaces.runs_for(workspace_id)
        return templates.TemplateResponse(
            request=request,
            name="workspace.html",
            context={
                "workspace": workspace,
                "messages": workspaces.messages_for(workspace_id),
                "runs": runs,
                "has_active_run": any(
                    run.status in {"queued", "running"} for run in runs
                ),
            },
        )

    @application.post("/workspaces/{workspace_id}/messages", include_in_schema=False)
    async def follow_up(
        workspace_id: str,
        username: Annotated[str, Depends(require_user)],
        content: Annotated[str, Form(min_length=1, max_length=20_000)],
    ) -> RedirectResponse:
        """Queue one follow-up without accepting client-controlled session data."""
        del username
        try:
            workspaces.add_follow_up(workspace_id, content)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Workspace not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return RedirectResponse(url=f"/workspaces/{workspace_id}", status_code=303)

    @application.post("/workspaces/{workspace_id}/rename", include_in_schema=False)
    async def rename_workspace(
        workspace_id: str,
        username: Annotated[str, Depends(require_user)],
        title: Annotated[str, Form(min_length=1, max_length=120)],
    ) -> RedirectResponse:
        del username
        if workspaces.get_workspace(workspace_id) is None:
            raise HTTPException(status_code=404, detail="Workspace not found.")
        workspaces.rename(workspace_id, title)
        return RedirectResponse(url=f"/workspaces/{workspace_id}", status_code=303)

    @application.post("/workspaces/{workspace_id}/archive", include_in_schema=False)
    async def archive_workspace(
        workspace_id: str,
        username: Annotated[str, Depends(require_user)],
    ) -> RedirectResponse:
        del username
        if workspaces.get_workspace(workspace_id) is None:
            raise HTTPException(status_code=404, detail="Workspace not found.")
        workspaces.archive(workspace_id)
        return RedirectResponse(url="/", status_code=303)

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
