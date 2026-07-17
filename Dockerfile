FROM node:22-bookworm-slim AS node-runtime

FROM golang:1.26.5-bookworm AS gog-builder

ARG GOGCLI_VERSION=v0.34.1
ARG GOGCLI_COMMIT=4747fb05a4290176716ddfd07340f684346a9c18
ARG GOGCLI_REPOSITORY=https://github.com/openclaw/gogcli.git

WORKDIR /src
COPY apps/agent-workbench/gog/techlett-google-readonly.yaml /tmp/techlett-google-readonly.yaml
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && git clone --depth 1 --branch "${GOGCLI_VERSION}" "${GOGCLI_REPOSITORY}" /src/gogcli \
    && cd /src/gogcli \
    && git rev-parse HEAD | grep -Fx "${GOGCLI_COMMIT}" \
    && mkdir -p /out \
    && go run ./cmd/bake-safety-profile /tmp/techlett-google-readonly.yaml internal/cmd/baked_safety_profile_gen.go \
    && go build -tags safety_profile -o /out/gog-safe ./cmd/gog

FROM python:3.12-slim AS runtime

ARG OPENCLAW_VERSION=2026.7.1

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system workbench \
    && adduser --system --ingroup workbench --home /home/workbench workbench \
    && mkdir -p /usr/local/lib/node_modules /google \
    && chmod 0700 /google \
    && chown -R workbench:workbench /google

COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node-runtime /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
COPY --from=gog-builder /out/gog-safe /usr/local/bin/gog

RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && npm install --global "openclaw@${OPENCLAW_VERSION}" \
    && openclaw --version \
    && chmod 0755 /usr/local/bin/gog \
    && /usr/local/bin/gog --version \
    && ! /usr/local/bin/gog gmail send --help >/dev/null 2>&1

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

CMD ["uvicorn", "agent_workbench.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
