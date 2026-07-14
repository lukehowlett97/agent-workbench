# Phase: Persistent Conversational Workspaces

## Objective

Evolve Agent Workbench from a one-shot batch processor into a persistent,
conversational analysis environment.

A workspace should retain its uploaded files, OpenClaw session, messages, runs
and generated artefacts. A user can inspect an initial result, ask follow-up
questions and progressively refine the analysis without uploading the same
files again.

## User outcome

A user can:

1. Create a workspace with a prompt and files.
2. Watch an OpenClaw run move through queued, running, completed or failed.
3. Read the result as a conversation message.
4. Ask a follow-up question in the same context.
5. Reuse the same isolated files and OpenClaw session.
6. View and download generated artefacts.
7. retry failures, rename the workspace, or archive it.

## Product model

The current job should become a **run**, owned by a longer-lived **workspace**.

```text
Workspace
├── OpenClaw session
├── input files
├── messages
├── runs
└── artefacts
```

- **Workspace:** persistent user-facing project and security boundary.
- **Message:** user instruction or assistant response displayed in sequence.
- **Run:** one queued execution triggered by a user message.
- **Artefact:** an uploaded or agent-generated file.
- **OpenClaw session:** persistent session identifier reused by workspace runs.

Each follow-up creates a new message and run. It must not mutate or reuse state
belonging to another workspace.

## Proposed data model

### `workspaces`

| Field | Purpose |
| --- | --- |
| `id` | UUID |
| `title` | User-editable display name |
| `status` | active or archived |
| `executor` | openclaw |
| `model` | Effective model identifier |
| `session_key` | Unique OpenClaw session key |
| `created_at` | Creation time |
| `updated_at` | Last activity time |

### `messages`

| Field | Purpose |
| --- | --- |
| `id` | UUID |
| `workspace_id` | Owning workspace |
| `role` | user, assistant or system-event |
| `content` | Displayable Markdown |
| `created_at` | Message time |
| `run_id` | Producing run when applicable |

### `runs`

| Field | Purpose |
| --- | --- |
| `id` | UUID |
| `workspace_id` | Owning workspace |
| `trigger_message_id` | User message that started the run |
| `status` | queued, running, completed, failed or cancelled |
| `executor` | Executor used |
| `model` | Effective model used |
| `created_at` | Queue time |
| `started_at` | Worker claim time |
| `completed_at` | Terminal time |
| `error_summary` | Safe bounded error |
| `duration_ms` | Measured execution time |

### `artefacts`

| Field | Purpose |
| --- | --- |
| `id` | UUID |
| `workspace_id` | Owning workspace |
| `run_id` | Producing run; null for uploads |
| `kind` | input or output |
| `original_name` | User-facing filename |
| `stored_name` | Safe internal filename |
| `media_type` | Detected content type |
| `size_bytes` | File size |
| `sha256` | Integrity hash |
| `created_at` | Creation time |

Use foreign keys and indexes on workspace, run status and creation times.

## Filesystem layout

```text
/data/workspaces/<workspace-id>/
├── input/
├── work/
├── output/
│   └── <run-id>/
└── manifests/
    └── <run-id>.json
```

The worker may read `input/` and its workspace history. It may write only to
the current run's output directory and controlled work directory.

## OpenClaw session behaviour

- Generate one unguessable session key per workspace.
- Reuse it for every follow-up in that workspace.
- Never accept a session key from form data or a URL.
- Store the key server-side.
- Resetting a conversation creates a new session key while retaining artefacts.
- Archiving a workspace prevents new runs but keeps existing results readable.
- Deleting a workspace removes its database records and filesystem tree through
  an explicit confirmed operation.
- Construct prompts so document contents remain untrusted data and cannot
  redefine system instructions.
- Do not display private chain-of-thought. Show only safe activity events and
  final responses.

## Interface

### Workspace list

Replace the flat recent-jobs list with:

- workspace title;
- last activity;
- latest run status;
- model;
- archive control;
- new-workspace action.

### Workspace detail

Use a three-area layout:

| Area | Contents |
| --- | --- |
| Left | Workspaces and workflow starters |
| Centre | Conversation, run status and follow-up composer |
| Right | Uploaded files and generated artefacts |

On small screens, collapse the side areas into drawers or stacked sections.

### Conversation

Display:

- user prompts;
- assistant Markdown responses;
- queued/running indicators;
- safe execution events;
- retry action for failures;
- timestamps and duration;
- executor and model metadata.

Poll only while a run is non-terminal. Stop polling on completed, failed or
cancelled states.

### Artefacts

Support:

- secure authenticated downloads;
- input/output distinction;
- filename, size and producing run;
- Markdown preview;
- CSV preview with bounded rows;
- Plotly HTML opening in a sandboxed context;
- PDF/image preview later.

Never serve files by accepting arbitrary filesystem paths.

## Workflow starters

Add starters after the general conversation is reliable:

1. Explore a dataset.
2. Analyse a time series.
3. Compare files.
4. Extract document evidence.
5. Generate a data-quality report.
6. Analyse GNSS observations.

A starter supplies versioned system instructions and an initial prompt template.
It must not grant additional tools implicitly.

## Implementation stages

### 1. Schema and migration

- Introduce workspace, message, run and artefact tables.
- Migrate existing jobs into one workspace and one run each.
- Preserve current result pages and file paths during transition.
- Add repository tests for ownership and lifecycle transitions.

### 2. Workspace routes

- Add workspace list, create, detail, rename and archive routes.
- Create initial user message and run transactionally.
- Keep authentication on every workspace and artefact route.
- Add not-found behaviour that does not disclose other workspace identifiers.

### 3. Conversational execution

- Reuse the stored OpenClaw session key.
- Build follow-up prompts from the new user message and controlled workspace
  context.
- Persist assistant output as a message.
- Record executor, model, timings and safe errors on every run.
- Prevent concurrent runs in the same workspace initially.

### 4. Conversation UI

- Render Markdown safely.
- Add follow-up composer.
- Add terminal-aware status polling.
- Add retry controls.
- Improve failed-state presentation and hide archived workspaces by default.

### 5. Artefacts

- Inventory uploads and generated files after each run.
- Persist hashes and metadata.
- Add authenticated download routes.
- Add bounded previews.
- Reject symlinks and files escaping the workspace root.

### 6. Retention and operations

- Add archive and confirmed deletion flows.
- Add retention settings for archived workspaces.
- Include database and workspace data in backups.
- Test restoration with an active conversation and generated artefacts.
- Add metrics for queue depth, run duration, failures and executor/model usage.

## Security requirements

- Keep `NVIDIA_API_KEY` worker-only.
- Keep the web and worker containers non-root with dropped capabilities.
- Do not mount the Docker socket or SSH material.
- Resolve and verify every filesystem path beneath the owning workspace.
- Reject symlinks, archives and unsupported content initially.
- Keep upload and workspace size limits.
- Use bounded subprocess timeouts and output sizes.
- Store safe error summaries without environment values, commands or
  tracebacks.
- Escape user content and sanitise rendered Markdown.
- Apply CSRF protection before exposing state-changing browser routes publicly.
- Keep the service loopback-only until public authentication, rate limiting,
  HTTPS and CSRF protections are complete.

## Testing

Cover:

- workspace creation;
- initial message and run transaction;
- follow-up session reuse;
- isolation between two workspaces;
- prevention of concurrent workspace runs;
- atomic queue claiming;
- worker restart recovery;
- failed-run retry;
- archive behaviour;
- path traversal and symlink rejection;
- authenticated artefact downloads;
- migration of existing jobs;
- backup and restore;
- OpenClaw adapter integration using a fake executable;
- one manual NVIDIA-backed end-to-end test.

## Acceptance criteria

This phase is complete when:

- A user can create and rename a workspace.
- Uploaded files remain available only to that workspace.
- A completed response appears as an assistant message.
- A follow-up reuses the same OpenClaw session and files.
- Two workspaces cannot access each other's state or artefacts.
- Run state updates without a full manual refresh.
- Generated files appear in the artefact panel and download securely.
- Failed runs can be retried without duplicating the user message.
- Executor, model, duration and timestamps are visible.
- Existing jobs migrate without data loss.
- Automated isolation and lifecycle tests pass.
- Backup restoration preserves the conversation and artefacts.

## Out of scope

- Multiple user accounts and shared workspaces.
- Public registration.
- Payments and quotas.
- Email, Slack, calendar or browser integrations.
- Scheduled autonomous agents.
- Unreviewed community skills.
- Visual workflow builders.
- Vector memory across separate workspaces.

## Recommended first delivery

Deliver the smallest vertical slice first:

1. Create a workspace from the existing form.
2. Store the prompt as a user message.
3. Run OpenClaw using a persistent workspace session key.
4. Store the response as an assistant message.
5. Add one follow-up composer.
6. Demonstrate that the second response uses the original CSV and conversation
   without another upload.

That slice proves the central product idea before investing in previews,
presets, richer activity events or public access.
