# Maintenance Agent Rules

1. Use only native maintenance tools.
2. Never use shell, Exec, SSH, Docker, package-manager, generic filesystem,
   preview-builder, or arbitrary Git tools.
3. Never invent packages, versions, commands, paths, image tags, or Compose options.
4. Never modify the maintenance broker, executor, policy registry, auth, or permissions.
5. Never request an unapproved dependency.
6. Never claim restart success until post-restart health checks pass.
7. Stop on terminal errors and do not repeat identical requests.
8. Treat Gateway replacement as asynchronous and poll by returned job ID.
