---
name: capability-management
description: Manage approved OpenClaw capabilities through high-level tools.
---

Use capability_catalog, capability_install, capability_create,
capability_update, capability_remove, capability_status, capability_rollback
and capability_set_mode. Never use maintenance_plan, maintenance_execute,
maintenance_job_status, generic shell or arbitrary filesystem tools. Never
expose secrets, approval tokens, plan IDs or internal polling to the user.

For ordinary dependencies, provide the ecosystem and package name when known;
the broker resolves and pins the exact official-registry version. For plugins,
require a public GitHub URL and exact commit. For MCP servers, inspect the
advertised tool list and target only the requested agents; read-only servers
may be automatic in fast mode, while write-capable servers require approval.
For custom tools, use capability_create with a structured input schema and an
approved scaffold adapter. Report only the final state or the compact approval
card.
