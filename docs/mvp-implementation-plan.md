# OpenClaw Agent Workbench — MVP Implementation Plan

## 1. Objective

Build a private web application at `agents.techlett.xyz` where a user can:

1. Enter a prompt.
2. Upload one or more files.
3. Submit the work as a background job.
4. View its progress and final response.
5. Download generated outputs.

The first release is a secure technical foundation, not a general autonomous assistant. It should make it easy to add named, repeatable workflows later.

## 2. MVP scope

### Included

- Single-user password authentication.
- Prompt entry and multiple-file upload.
- One general workflow: **Analyse the supplied files and produce a report**.
- Background job execution with queued, running, completed and failed states.
- NVIDIA NIM model access through its OpenAI-compatible API.
- OpenClaw as the agent runtime.
- Per-job isolated input, working and output directories.
- Job history with timestamps and status.
- Markdown response display.
- Downloadable generated files.
- Docker Compose deployment through `vps_stuff`.
- HTTPS through Nginx at `agents.techlett.xyz`.
- Basic logging, retention and backup documentation.

### Excluded from the MVP

- Public registration or multiple users.
- Payments and usage billing.
- Email, Slack, browser or third-party account access.
- Scheduled or continuously running agents.
- Unreviewed community OpenClaw skills.
- Unrestricted shell access.
- Vector databases or long-term semantic memory.
- Complex workflow builder.
- Local model hosting.

## 3. Repository ownership

Create a standalone public application repository named `agent-workbench`, included as a Git submodule in `vps_stuff`.

```text
vps_stuff/
├── apps/
│   └── agent-workbench/          # Git submodule
├── compose/
│   └── agent-workbench.yml
├── deployments/
│   └── agents.techlett.xyz.env.example
├── nginx/
│   └── sites-available/
│       └── agents.techlett.xyz
└── docs/
    └── agent-workbench.md
```

### `agent-workbench` owns

- Web frontend.
- FastAPI service.
- Job model and database access.
- OpenClaw adapter and approved configuration.
- File extraction and validation.
- Workflow prompts.
- Automated tests.
- Application-level documentation.

### `vps_stuff` owns

- Git submodule reference.
- Docker Compose deployment definition.
- Nginx and domain configuration.
- Environment-variable template.
- Deployment, rollback, backup and restoration commands.
- VPS-specific operations documentation.

OpenClaw should be pinned to an explicit image or package version. Its source should not be copied into either repository.

## 4. Proposed architecture

```text
Browser
  -> Nginx / HTTPS
  -> FastAPI application
       -> SQLite job database
       -> Job queue
       -> Isolated OpenClaw worker
            -> NVIDIA NIM API
            -> Per-job workspace
```

For the first version, a database-backed internal queue and a dedicated worker process are sufficient. Avoid Redis and Celery until concurrency or reliability requirements justify them.

### Suggested components

- **Backend:** Python 3.12, FastAPI, SQLAlchemy and Alembic.
- **Database:** SQLite stored on a persistent volume.
- **Frontend:** server-rendered templates with modest JavaScript, or the smallest existing frontend pattern that fits the portfolio.
- **Agent provider:** NVIDIA NIM at `https://integrate.api.nvidia.com/v1`.
- **Initial model candidate:** `nvidia/nemotron-3-super-120b-a12b`.
- **Deployment:** Docker Compose behind the existing VPS Nginx service.

## 5. Data model

The initial `jobs` table should contain:

| Field | Purpose |
| --- | --- |
| `id` | UUID exposed to the interface |
| `status` | queued, running, completed or failed |
| `prompt` | User instruction |
| `model` | Model identifier used for the run |
| `created_at` | Submission time |
| `started_at` | Worker start time |
| `completed_at` | Completion or failure time |
| `result_markdown` | Final textual response |
| `error_summary` | Safe user-facing failure detail |
| `workspace_path` | Internal per-job storage reference |

Store uploaded and generated file metadata separately so the database does not contain file bytes.

## 6. Per-job filesystem layout

```text
/data/jobs/<job-id>/
├── input/
├── work/
├── output/
└── manifest.json
```

- Uploaded files are saved only under `input/`.
- Agent scratch work is confined to `work/`.
- Only files under `output/` can be downloaded.
- Filenames are normalised and assigned safe internal names.
- The manifest records original names, sizes, hashes and generated outputs.

## 7. Security boundaries

Treat uploaded files and their contents as untrusted.

- Require authentication for every route except `/health`.
- Enforce a conservative upload limit, initially 25 MB per file and 100 MB per job.
- Allow only an explicit initial set of formats, such as `.txt`, `.md`, `.csv`, `.json` and `.pdf`.
- Reject archive files and executable content.
- Prevent path traversal by generating internal filenames.
- Run the worker as a non-root user.
- Mount only its job workspace as writable.
- Do not mount the Docker socket, SSH directory, application source or other VPS data.
- Do not provide unrestricted network, browser or shell tools.
- Permit outbound traffic only as narrowly as deployment facilities allow.
- Keep `NVIDIA_API_KEY` in a VPS environment file, never Git.
- Apply CPU, memory, process and execution-time limits.
- Redact secrets and internal paths from user-visible errors and logs.
- Pin and review every OpenClaw skill or extension before enabling it.
- Automatically remove jobs and files after a configurable retention period, initially seven days.

## 8. Implementation stages

### Stage 0 — Validate the critical integration

Before building the interface:

1. Obtain an NVIDIA API key.
2. Call the selected NIM model directly using its OpenAI-compatible endpoint.
3. Confirm that normal chat completions work.
4. Run a minimal OpenClaw session against the same endpoint.
5. Test tool calling and structured output.
6. Record the working model configuration, latency and known limits.

**Exit criterion:** A local command can run OpenClaw with NVIDIA NIM, read a sample file from an isolated directory and write a predictable result.

### Stage 1 — Scaffold the application repository

1. Create the standalone `agent-workbench` Git repository.
2. Add Python project configuration, linting and tests.
3. Add FastAPI with `/health` and a minimal authenticated page.
4. Add the pinned OpenClaw dependency or image configuration.
5. Add `.env.example` without secrets.
6. Add a local Docker Compose setup.

**Exit criterion:** A new developer can clone the repository, configure an API key and open the authenticated application locally.

### Stage 2 — Implement jobs and uploads

1. Add the database schema and migrations.
2. Build the job submission form.
3. Validate upload extensions, MIME types and sizes.
4. Create the per-job workspace and manifest.
5. Save the queued job transactionally.
6. Add job history and job detail pages.

**Exit criterion:** A prompt and valid files create a durable queued job; invalid or oversized files are rejected safely.

### Stage 3 — Add the isolated worker

1. Implement a single-worker job loop.
2. Atomically claim one queued job.
3. Construct the approved OpenClaw session and workflow prompt.
4. Expose only input reading and output writing tools.
5. Call NVIDIA NIM and capture the result.
6. Store final Markdown, output metadata and safe failure information.
7. Recover jobs left in `running` after a worker restart.

**Exit criterion:** Submitting a supported document produces a completed job and report without granting the agent access outside its job workspace.

### Stage 4 — Complete the user experience

1. Show queued and running states with polling.
2. Render final Markdown safely.
3. List generated files with download links.
4. Add clear empty, validation and failure states.
5. Add a sample prompt and supported-format guidance.
6. Display model and completion timestamps.

**Exit criterion:** The complete prompt-upload-result flow works without terminal access and failures are understandable.

### Stage 5 — Integrate with `vps_stuff`

1. Add `agent-workbench` under `apps/` as a submodule.
2. Add the production Compose definition and persistent volumes.
3. Add the environment template and secret-placement instructions.
4. Add Nginx configuration for `agents.techlett.xyz`.
5. Add deploy, health-check and rollback targets.
6. Add backup and blank-VPS restoration documentation.
7. Deploy behind HTTPS and verify authentication.

**Exit criterion:** The service can be deployed and restored using only the repositories plus separately supplied secrets and backed-up application data.

### Stage 6 — Harden and verify

1. Test path traversal, duplicate filenames and malicious filenames.
2. Test unsupported, empty, malformed and oversized files.
3. Test prompt injection contained inside uploaded documents.
4. Test model timeout, rate-limit and malformed-response handling.
5. Restart the API and worker during queued and running jobs.
6. Confirm the container cannot read unrelated VPS paths.
7. Confirm secrets do not appear in logs, errors or generated outputs.
8. Run a backup and restoration rehearsal.

**Exit criterion:** The MVP acceptance tests pass and the documented restoration procedure works.

## 9. MVP acceptance criteria

The MVP is complete when:

- The site is available over HTTPS and requires authentication.
- A user can upload supported files with a prompt.
- The work continues if the browser is closed.
- Job state survives an application restart.
- A completed job presents Markdown and downloadable outputs.
- Failures are recorded without exposing secrets.
- The OpenClaw worker cannot access other VPS application data.
- Uploaded data expires according to the retention setting.
- Deployment and restoration are documented in `vps_stuff`.
- At least one automated end-to-end test covers the successful path.

## 10. Initial testing dataset

Use a small, non-sensitive fixture pack:

- One CSV time series containing missing values and obvious outliers.
- One short PDF describing the dataset.
- One Markdown file containing misleading instructions to test prompt-injection resistance.

Expected output:

- A concise data-quality summary.
- Identified anomalies and assumptions.
- A generated Markdown report saved under `output/`.
- No execution of instructions embedded in the uploaded documents.

## 11. Decisions to defer

Do not decide these until the base flow has been exercised:

- Whether SQLite needs replacing with PostgreSQL.
- Whether the internal worker should become Celery, Dramatiq or another queue.
- Whether the frontend warrants a separate JavaScript framework.
- Which specialist workflows should be productised first.
- Whether users need editable workflow definitions.
- Whether to support additional model providers.
- Whether generated PDFs should be part of the default workflow.

## 12. Recommended first working session

The first implementation session should focus only on Stage 0:

1. Create the NVIDIA API key.
2. Select two candidate models.
3. Verify basic completions for both.
4. Verify OpenClaw can use the endpoint.
5. Test one file-reading and report-writing tool call.
6. Choose the initial model based on correctness and tool reliability rather than benchmark scores alone.

This removes the largest technical uncertainty before repository scaffolding or VPS changes begin.
