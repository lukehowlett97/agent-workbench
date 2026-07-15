---
name: openclaw-maintenance
description: Safely plan and execute approved OpenClaw runtime maintenance.
---

# OpenClaw maintenance

Understand the requested capability, inspect approved capabilities, create a
plan, present its risk and approval requirement, and execute only when the
broker permits it. Poll the returned job ID with bounded attempts and report
healthy, failed, rolling-back, or rolled-back state.

Use `maintenance_capabilities`, `maintenance_plan`, `maintenance_execute`,
`maintenance_job_status`, and `maintenance_status` only. Use
`maintenance_rollback` only when the operator explicitly requests it. Never
run CLI commands, inspect `.git`, invent dependencies, or retry terminal
failures.
