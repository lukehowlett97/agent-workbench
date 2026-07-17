---
name: openclaw-maintenance
description: Safely plan and execute approved OpenClaw runtime maintenance.
---

# OpenClaw maintenance

Understand the requested capability and use the high-level apply tool for
normal approved actions. It returns the final result for automatic actions or
a pending approval card for operator actions.

Use `maintenance_apply` for normal approved actions. Keep
`maintenance_capabilities`, `maintenance_plan`, `maintenance_execute`,
`maintenance_job_status`, and `maintenance_status` for diagnostics and
administrative workflows. Use `maintenance_rollback` only when the operator
explicitly requests it. Never request or expose approval tokens or signing
secrets, ask the user to copy a plan ID, construct JSON, or manually poll a
job. Never run CLI commands, inspect `.git`, invent dependencies, or retry
terminal failures. Report the final outcome in plain language.
