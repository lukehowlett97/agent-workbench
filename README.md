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
- Stage 1: authenticated FastAPI application shell.
- Next: persistent jobs, uploads and the isolated worker.

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
WORKBENCH_EXECUTOR=fixture    # tests and development
WORKBENCH_EXECUTOR=openclaw   # VPS production
```

The `openclaw` executor uses `OPENCLAW_VERSION`, `WORKBENCH_MODEL` and the
NVIDIA-compatible API configured by `NVIDIA_API_KEY`. Compose passes that key
only to the worker; the web container never receives it.

Alternatively:

```bash
make compose-up
```

The Compose service listens only on <http://127.0.0.1:18090>.

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

Uploaded files are untrusted input. The eventual agent worker will be isolated
from SSH keys, the Docker socket, application source and unrelated VPS data.
The Stage 1 container already runs as a non-root user with a read-only
filesystem, dropped Linux capabilities and no-new-privileges.

## Licence

No licence has been selected yet.
