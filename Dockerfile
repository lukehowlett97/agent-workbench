FROM node:22-bookworm-slim AS node-runtime

FROM python:3.12-slim AS runtime

ARG OPENCLAW_VERSION=2026.7.1

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system workbench \
    && adduser --system --ingroup workbench --home /home/workbench workbench \
    && mkdir -p /usr/local/lib/node_modules

COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node-runtime /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm

RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && npm install --global "openclaw@${OPENCLAW_VERSION}" \
    && openclaw --version

COPY apps/agent-workbench/pyproject.toml apps/agent-workbench/README.md ./
COPY apps/agent-workbench/src ./src
COPY deploy/gateway ./deploy/gateway
COPY deploy/maintenance/policy ./deploy/maintenance/policy
COPY apps/agent-workbench/agent-assets ./agent-assets

RUN python -m pip install --upgrade pip \
    && python -m pip install . \
    && python /app/deploy/gateway/install-approved-dependencies.py

USER workbench

EXPOSE 8000 18789

CMD ["uvicorn", "agent_workbench.main:app", "--host", "0.0.0.0", "--port", "8000"]
