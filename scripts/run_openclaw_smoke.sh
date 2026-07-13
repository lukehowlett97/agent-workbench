#!/usr/bin/env bash
set -euo pipefail

OPENCLAW_VERSION="2026.6.11"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_ROOT="${RUN_ROOT:-${ROOT_DIR}/.stage0}"
WORKSPACE="${RUN_ROOT}/workspace"

if [[ -z "${NVIDIA_API_KEY:-}" ]]; then
  echo "NVIDIA_API_KEY is required." >&2
  exit 2
fi

command -v node >/dev/null || {
  echo "Node.js is required." >&2
  exit 2
}

mkdir -p "${RUN_ROOT}/state" "${WORKSPACE}/input" "${WORKSPACE}/output"
rm -rf "${WORKSPACE}/input" "${WORKSPACE}/output"
mkdir -p "${WORKSPACE}/input" "${WORKSPACE}/output"
cp -R "${ROOT_DIR}/fixtures/input/." "${WORKSPACE}/input/"
cp "${ROOT_DIR}/openclaw/openclaw.example.json5" "${RUN_ROOT}/state/openclaw.json"

export OPENCLAW_STATE_DIR="${RUN_ROOT}/state"
export OPENCLAW_CONFIG_PATH="${RUN_ROOT}/state/openclaw.json"

OPENCLAW=(npx --yes "openclaw@${OPENCLAW_VERSION}")

"${OPENCLAW[@]}" config set agents.defaults.workspace "${WORKSPACE}"
"${OPENCLAW[@]}" doctor --lint
"${OPENCLAW[@]}" models list --provider nvidia
"${OPENCLAW[@]}" agent \
  --local \
  --agent main \
  --session-key "agent:main:stage0-smoke" \
  --message-file "${ROOT_DIR}/fixtures/task.md" \
  --timeout 300 \
  --json | tee "${RUN_ROOT}/openclaw-result.json"

REPORT="${WORKSPACE}/output/report.md"
if [[ ! -s "${REPORT}" ]]; then
  echo "OpenClaw completed without creating ${REPORT}." >&2
  exit 1
fi

echo "Smoke test passed: ${REPORT}"
