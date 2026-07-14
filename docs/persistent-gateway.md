# Persistent OpenClaw Gateway

This phase replaces per-job local OpenClaw startup with one long-lived,
authenticated Gateway. The existing `openclaw` executor remains available as
a rollback path; select the new path with
`WORKBENCH_EXECUTOR=openclaw-gateway`.

## Topology

- `web` accepts authenticated prompts and uploads, and writes job data.
- `worker` claims jobs and invokes the OpenClaw CLI as a remote Gateway client.
- `gateway` owns the OpenClaw runtime, model connection and session state.
- `NVIDIA_API_KEY` is supplied only to `gateway`.
- `OPENCLAW_GATEWAY_TOKEN` is shared only by `gateway` and `worker`.
- The Gateway port is exposed only on the private Compose network.

Each job receives a unique session key,
`agent:main:workbench:<job-id>`, and its own input, work and output
directories. Gateway state survives container replacement in the
`openclaw-state` volume.

## Enable it on the VPS

From `/srv/projects/agent-workbench`:

```bash
openssl rand -hex 32
```

Store the result in the existing private `.env`:

```dotenv
WORKBENCH_EXECUTOR=openclaw-gateway
OPENCLAW_GATEWAY_TOKEN=<generated-token>
OPENCLAW_GATEWAY_URL=ws://gateway:18789
OPENCLAW_GATEWAY_TIMEOUT_SECONDS=300
```

Keep the existing `NVIDIA_API_KEY` and `WORKBENCH_MODEL`. Then build and
start the new topology:

```bash
docker compose build
docker compose up -d
docker compose ps
docker compose logs --tail=100 gateway worker
```

The Gateway health check must pass before Compose starts the worker. Submit a
small prompt from the interface and confirm the result page shows:

```text
Executor: openclaw-gateway
```

## Expected latency improvement

The Gateway removes repeated package resolution and OpenClaw runtime startup
from the job path. Model inference and agent tool use still dominate longer
jobs, so measure rather than assuming an exact target.

Record at least five identical no-file prompts before and after migration.
Compare median queue-to-completion time, and separately inspect Gateway logs
for agent runtime duration. A useful first target is a warm trivial response in
under 15 seconds.

## Rollback

The prior executor still exists in the application:

```dotenv
WORKBENCH_EXECUTOR=openclaw
```

That executor requires `NVIDIA_API_KEY` in the worker. The persistent
Gateway Compose topology deliberately does not provide it there. For a
temporary rollback, use a private Compose override that restores the variable
to the worker, or redeploy the previous known-good commit.

## Security boundary

This is suitable for a private, single-user workbench. It is not yet a
multi-tenant sandbox.

The Gateway mounts the shared `/data/jobs` tree because one long-lived agent
must reach each assigned workspace. Prompt instructions tell the agent to
remain inside the current job, but that is not an operating-system boundary.
Before exposing the service to untrusted users, run jobs in separate
containers or mount only one job into a disposable execution sandbox.

Do not publish port 18789. Rotate `OPENCLAW_GATEWAY_TOKEN` if it is exposed,
and never put either token or NVIDIA key in job output or application logs.

## Next increments

1. Stream Gateway lifecycle events into the result page.
2. Add a conversation entity with deliberate session reuse.
3. Add named workflow templates with allowed tools and output schemas.
4. Mount reviewed OpenClaw skills read-only and enable them per workflow.
5. Replace shared job storage access with disposable per-job sandboxes.
