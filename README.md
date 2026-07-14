# Agent Workbench

A secure, self-hosted interface for prompt-driven file analysis workflows.

The MVP combines:

- a private web interface for prompts and file uploads;
- OpenClaw as the agent runtime;
- NVIDIA NIM as an OpenAI-compatible model endpoint;
- isolated per-job workspaces;
- background processing and downloadable outputs;
- reproducible deployment through `vps_stuff`.

See [the MVP implementation plan](docs/mvp-implementation-plan.md).

## Current status

- Stage 0: NVIDIA NIM chat and tool calling validated.
- Authenticated FastAPI interface, persistent jobs and file uploads.
- Background worker with local and persistent Gateway OpenClaw executors.
- Next: streamed progress, conversations, workflows and reviewed skills.

Nemotron 3 Super is the current primary model because initial testing showed
cleaner instruction following and substantially lower latency than Ultra.

## Local setup

Requirements:

- Python 3.12 or later;
- Node.js for OpenClaw validation;
- an NVIDIA API key from [build.nvidia.com](https://build.nvidia.com/settings/api-keys).

Create the local environment:

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Populate `.env` with the complete NVIDIA key and private interface
credentials. The file is excluded from Git.

Run validation:

```bash
python scripts/validate_nim.py --output .stage0/nim-results.json
bash scripts/run_openclaw_smoke.sh
```

Both scripts load `.env` automatically. The OpenClaw test uses isolated state
under `.stage0/` and must create
`.stage0/workspace/output/report.md`.

## Run the web application

With `WORKBENCH_USERNAME` and `WORKBENCH_PASSWORD` configured:

```bash
make run
```

Open <http://127.0.0.1:8000/> and authenticate using the configured
credentials. The unauthenticated liveness endpoint is
<http://127.0.0.1:8000/health>.

Executor selection is explicit:

```bash
WORKBENCH_EXECUTOR=fixture             # tests and development
WORKBENCH_EXECUTOR=openclaw            # one local runtime per job
WORKBENCH_EXECUTOR=openclaw-gateway    # persistent VPS Gateway
```

The recommended `openclaw-gateway` executor submits jobs to one authenticated,
long-lived Gateway. Compose passes `NVIDIA_API_KEY` only to that Gateway; the
web and worker containers never receive it. See
[the persistent Gateway deployment guide](docs/persistent-gateway.md).

Alternatively:

```bash
make compose-up
```

The Compose service listens only on <http://127.0.0.1:18090>.

## Work modes

The interface separates three kinds of work:

- **Ask** provides direct answers and accepts optional supporting files.
- **Analyse** investigates one or more uploaded files using a free-form brief.
- **Workflow** applies a reviewed prompt template with explicit file requirements.

The initial workflows cover file summarisation, action extraction, document
comparison and tabular data-quality review. A job stores both the user's
original request and the reviewed execution prompt, together with its mode and
workflow identifier. This provides a safe path towards enabling selected
OpenClaw skills per workflow later.

## Checks

```bash
make lint
make test
```

## Repository and deployment

This repository is included under `vps_stuff/apps/agent-workbench` as a Git
submodule. `vps_stuff` owns the production Compose definition, Nginx
configuration, deployment, backups and restoration documentation.

## Security

Uploaded files are untrusted input. The services run as a non-root user with a
read-only filesystem, dropped Linux capabilities and no-new-privileges. The
persistent Gateway currently sees the shared jobs volume, so it is a
single-user security boundary rather than a multi-tenant sandbox.

## Licence

No licence has been selected yet.
