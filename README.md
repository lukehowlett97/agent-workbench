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
