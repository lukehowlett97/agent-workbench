# Agent Workbench

A secure, self-hosted interface for prompt-driven file analysis workflows.

The initial MVP will combine:

- a private web interface for prompts and file uploads;
- OpenClaw as the agent runtime;
- NVIDIA NIM as an OpenAI-compatible model endpoint;
- isolated per-job workspaces;
- background processing and downloadable outputs;
- reproducible deployment through `vps_stuff`.

## Status

Planning and integration validation.

The first technical milestone is to verify that OpenClaw can reliably use NVIDIA NIM for chat completions, tool calls, file reading and report writing.

See [the MVP implementation plan](docs/mvp-implementation-plan.md).

## Planned deployment

The application will be maintained as a standalone repository and included under `vps_stuff/apps/agent-workbench` as a Git submodule.

## Security

Uploaded files are untrusted input. The agent worker will be isolated from SSH keys, the Docker socket, application source and unrelated VPS data.

## Licence

No licence has been selected yet.


## Stage 0 validation

Requirements:

- Python 3.12 or later;
- Node.js;
- an NVIDIA API key from [build.nvidia.com](https://build.nvidia.com/settings/api-keys).

Keep the key in your shell environment:

```bash
export NVIDIA_API_KEY="nvapi-..."
```

Install the Python validation dependency and compare the candidate models:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python scripts/validate_nim.py --output .stage0/nim-results.json
```

Then run the pinned OpenClaw smoke test:

```bash
bash scripts/run_openclaw_smoke.sh
```

The smoke test uses an isolated state directory and job workspace under
`.stage0/`. It analyses the fixture files and must create
`.stage0/workspace/output/report.md`.

No API keys, generated reports or OpenClaw state are committed.
