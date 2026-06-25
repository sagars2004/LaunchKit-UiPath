#!/usr/bin/env bash
# Run LaunchKit UiPath coding-agent analyze from repo root.
# Usage: ./scripts/coding_agent.sh [claude|cursor|codex|gemini]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

: "${RUN_ID:?Set RUN_ID in .env (run ./scripts/pipeline.sh create first)}"
: "${LAUNCHKIT_API_SECRET:?Set LAUNCHKIT_API_SECRET in .env}"
: "${API_URL:=https://launchkit-uipath.onrender.com}"

CODING_TOOL="${1:-cursor}"

cd uipath_coded_process
exec uv run uipath run analyze_with_coding_agent "$(cat <<EOF
{
  "run_id": "$RUN_ID",
  "api_url": "$API_URL",
  "api_secret": "$LAUNCHKIT_API_SECRET",
  "coding_tool": "$CODING_TOOL"
}
EOF
)"
