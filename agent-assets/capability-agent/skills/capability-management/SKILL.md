---
name: capability-management
description: Manage approved OpenClaw capabilities through high-level tools.
---

Use capability_catalog, capability_install, capability_create,
capability_update, capability_remove, capability_status, capability_rollback
and capability_set_mode. Never use maintenance_plan, maintenance_execute,
maintenance_job_status, generic shell or arbitrary filesystem tools. Never
expose secrets, approval tokens, plan IDs or internal polling to the user.
