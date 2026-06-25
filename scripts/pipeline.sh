#!/usr/bin/env bash
# =============================================================================
# LaunchKit Pipeline Commands
# =============================================================================
#
# Usage:
#   source .env
#   ./scripts/pipeline.sh help              # list all commands
#   ./scripts/pipeline.sh health            # check API + LLM + Supabase
#   ./scripts/pipeline.sh create            # create a new run (prints RUN_ID)
#   ./scripts/pipeline.sh intel             # Step 1 — hackathon intel
#   ./scripts/pipeline.sh analyze           # Step 2 — code analysis
#   ./scripts/pipeline.sh generate          # Step 3 — artifacts + scoring
#   ./scripts/pipeline.sh artifacts         # list all artifacts + scores
#   ./scripts/pipeline.sh approve-all       # approve all 5 artifacts
#   ./scripts/pipeline.sh publish           # publish approved artifacts
#   ./scripts/pipeline.sh export            # download zip
#   ./scripts/pipeline.sh all               # run create → intel → analyze → generate
#
# Set RUN_ID to continue an existing run:
#   export RUN_ID="997342eb-3448-4218-9aef-910ffb7ecc2b"
#   ./scripts/pipeline.sh analyze
#
# Switch test case preset:
#   PRESET=fastapi ./scripts/pipeline.sh create
#   PRESET=uipath  ./scripts/pipeline.sh all
#   PRESET=custom  GITHUB_URL=... HACKATHON_URL=... ./scripts/pipeline.sh create
#
# =============================================================================

set -euo pipefail

# Auto-load .env from project root (exports all vars including RUN_ID)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
if [[ -f "${PROJECT_ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${PROJECT_ROOT}/.env"
  set +a
fi

# ── Connection ────────────────────────────────────────────────────────────────
API_URL="${API_URL:-http://localhost:8000}"
SECRET="${LAUNCHKIT_API_SECRET:-}"
AUTH="Authorization: Bearer ${SECRET}"
CT="Content-Type: application/json"

# ── Test case presets ─────────────────────────────────────────────────────────
# PRESET: fastapi | uipath | minimal | custom
PRESET="${PRESET:-uipath}"

case "${PRESET}" in
  fastapi)
    GITHUB_URL="${GITHUB_URL:-https://github.com/tiangolo/fastapi}"
    HACKATHON_URL="${HACKATHON_URL:-https://devpost.com/hackathons}"
    HACKATHON_NAME="${HACKATHON_NAME:-Devpost Hackathons}"
    TRACK_CATEGORY="${TRACK_CATEGORY:-General}"
    ;;
  uipath)
    GITHUB_URL="${GITHUB_URL:-https://github.com/tiangolo/fastapi}"
    HACKATHON_URL="${HACKATHON_URL:-https://uipath-agenthack.devpost.com/}"
    HACKATHON_NAME="${HACKATHON_NAME:-UiPath AgentHack}"
    TRACK_CATEGORY="${TRACK_CATEGORY:-Maestro BPMN}"
    ;;
  minimal)
    GITHUB_URL="${GITHUB_URL:-https://github.com/tiangolo/fastapi}"
    HACKATHON_URL="${HACKATHON_URL:-https://devpost.com/hackathons}"
    HACKATHON_NAME="${HACKATHON_NAME:-Test Hackathon}"
    TRACK_CATEGORY="${TRACK_CATEGORY:-}"
    ;;
  custom)
    GITHUB_URL="${GITHUB_URL:?Set GITHUB_URL for PRESET=custom}"
    HACKATHON_URL="${HACKATHON_URL:?Set HACKATHON_URL for PRESET=custom}"
    HACKATHON_NAME="${HACKATHON_NAME:-Custom Hackathon}"
    TRACK_CATEGORY="${TRACK_CATEGORY:-}"
    ;;
  *)
    echo "Unknown PRESET=${PRESET}. Use: fastapi | uipath | minimal | custom"
    exit 1
    ;;
esac

# Existing run (set to skip create)
RUN_ID="${RUN_ID:-}"

# ── Helpers ───────────────────────────────────────────────────────────────────
_require_secret() {
  if [[ -z "${SECRET}" ]]; then
    echo "ERROR: LAUNCHKIT_API_SECRET is not set. Add it to .env or export it."
    exit 1
  fi
}

_require_run_id() {
  if [[ -z "${RUN_ID}" ]]; then
    echo "ERROR: RUN_ID is not set. Run './scripts/pipeline.sh create' first or export RUN_ID=..."
    exit 1
  fi
}

_print_preset() {
  echo "Preset:    ${PRESET}"
  echo "GitHub:    ${GITHUB_URL}"
  echo "Hackathon: ${HACKATHON_URL}"
  echo "Name:      ${HACKATHON_NAME}"
  echo "Track:     ${TRACK_CATEGORY}"
  echo "RUN_ID:    ${RUN_ID:-<not set>}"
  echo "API:       ${API_URL}"
}

# =============================================================================
# COMMANDS — copy individual blocks below if you prefer raw curl
# =============================================================================

cmd_help() {
  cat <<'EOF'
LaunchKit pipeline commands:

  health        GET  /health
  create        POST /api/v1/runs
  get           GET  /api/v1/runs/{id}
  intel         POST /api/v1/runs/{id}/intel          Step 1 (sync — slow)
  intel-start   POST /api/v1/runs/{id}/intel/start    Step 1 async (Maestro)
  wait-intel    Poll /pipeline-status until intel_ready
  analyze       POST /api/v1/runs/{id}/analyze        Step 2
  generate      POST /api/v1/runs/{id}/generate       Step 3
  artifacts     GET  /api/v1/runs/{id}/artifacts
  artifact      GET  /api/v1/runs/{id}/artifacts/{type}
  approve       POST /api/v1/runs/{id}/artifacts/{type}/approve
  approve-all   Approve readme, devpost_copy, demo_script, social_content, blog_draft
  revise        POST /api/v1/runs/{id}/artifacts/{type}/revise  (needs FEEDBACK env)
  publish       POST /api/v1/runs/{id}/publish
  export        GET  /api/v1/runs/{id}/export → launchkit-{id}.zip
  metrics       GET  /api/v1/runs/{id}/metrics
  poll-metrics  POST /api/v1/runs/{id}/metrics/poll
  retrospective POST /api/v1/runs/{id}/retrospective/generate
  all           create → intel → analyze → generate
  preset        Show current PRESET config

Environment:
  PRESET          fastapi | uipath | minimal | custom
  RUN_ID          Continue an existing run
  GITHUB_URL      Override repo (with PRESET=custom or any preset)
  HACKATHON_URL   Override hackathon URL
  LAUNCHKIT_API_SECRET / API_URL
  FEEDBACK        Text for revise command
  ARTIFACT_TYPE   Artifact for artifact/approve/revise (default: readme)

Examples:
  source .env && ./scripts/pipeline.sh health
  PRESET=uipath ./scripts/pipeline.sh create
  export RUN_ID=... && ./scripts/pipeline.sh intel
  FEEDBACK="Add more detail" ARTIFACT_TYPE=devpost_copy ./scripts/pipeline.sh revise
  PRESET=custom GITHUB_URL=https://github.com/you/repo HACKATHON_URL=https://... ./scripts/pipeline.sh all
EOF
}

cmd_preset() {
  _print_preset
}

cmd_health() {
  curl -s "${API_URL}/health" | python3 -m json.tool
}

cmd_create() {
  _print_preset
  echo ""
  echo "==> Creating run..."
  RESP=$(curl -s -X POST "${API_URL}/api/v1/runs" \
    -H "${AUTH}" -H "${CT}" \
    -d "{
      \"github_url\": \"${GITHUB_URL}\",
      \"hackathon_url\": \"${HACKATHON_URL}\",
      \"hackathon_name\": \"${HACKATHON_NAME}\",
      \"track_category\": \"${TRACK_CATEGORY}\"
    }")
  echo "${RESP}" | python3 -m json.tool
  RUN_ID=$(echo "${RESP}" | python3 -c "import sys,json; print(json.load(sys.stdin)['run_id'])")
  echo ""
  echo "export RUN_ID=${RUN_ID}"
}

cmd_get() {
  _require_run_id
  curl -s "${API_URL}/api/v1/runs/${RUN_ID}" -H "${AUTH}" | python3 -m json.tool
}

cmd_intel() {
  _require_run_id
  echo "==> Step 1: Intelligence gathering..."
  curl -s -X POST "${API_URL}/api/v1/runs/${RUN_ID}/intel" -H "${AUTH}" | python3 -m json.tool
}

cmd_intel_start() {
  _require_run_id
  echo "==> Step 1: Start intelligence (async)..."
  curl -s -X POST "${API_URL}/api/v1/runs/${RUN_ID}/intel/start" -H "${AUTH}" | python3 -m json.tool
}

cmd_wait_intel() {
  _require_run_id
  echo "==> Waiting for intel to complete..."
  for _ in $(seq 1 40); do
    status=$(curl -s "${API_URL}/api/v1/runs/${RUN_ID}/pipeline-status" -H "${AUTH}")
    ready=$(echo "${status}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('intel_ready', False))")
    failed=$(echo "${status}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('failed', False))")
    if [[ "${ready}" == "True" ]]; then
      echo "${status}" | python3 -m json.tool
      return 0
    fi
    if [[ "${failed}" == "True" ]]; then
      echo "Intel failed:" >&2
      echo "${status}" | python3 -m json.tool >&2
      return 1
    fi
    sleep 15
  done
  echo "Timed out waiting for intel" >&2
  return 1
}

cmd_analyze() {
  _require_run_id
  echo "==> Step 2: Code analysis..."
  curl -s -X POST "${API_URL}/api/v1/runs/${RUN_ID}/analyze" -H "${AUTH}" | python3 -m json.tool
}

cmd_generate() {
  _require_run_id
  echo "==> Step 3: Content generation + quality scoring (may take 1-3 min)..."
  curl -s -X POST "${API_URL}/api/v1/runs/${RUN_ID}/generate" -H "${AUTH}" | python3 -m json.tool
}

cmd_artifacts() {
  _require_run_id
  curl -s "${API_URL}/api/v1/runs/${RUN_ID}/artifacts" -H "${AUTH}" | python3 -m json.tool
}

cmd_artifact() {
  _require_run_id
  local type="${ARTIFACT_TYPE:-readme}"
  curl -s "${API_URL}/api/v1/runs/${RUN_ID}/artifacts/${type}" -H "${AUTH}" | python3 -m json.tool
}

cmd_approve() {
  _require_run_id
  local type="${ARTIFACT_TYPE:-readme}"
  curl -s -X POST "${API_URL}/api/v1/runs/${RUN_ID}/artifacts/${type}/approve" \
    -H "${AUTH}" | python3 -m json.tool
}

cmd_approve_all() {
  _require_run_id
  for type in readme devpost_copy demo_script social_content blog_draft; do
    echo "==> Approving ${type}..."
    curl -s -X POST "${API_URL}/api/v1/runs/${RUN_ID}/artifacts/${type}/approve" -H "${AUTH}"
    echo ""
  done
}

cmd_revise() {
  _require_run_id
  local type="${ARTIFACT_TYPE:-devpost_copy}"
  local feedback="${FEEDBACK:-Add more technical detail and mention UiPath Maestro BPMN orchestration.}"
  echo "==> Revising ${type}..."
  curl -s -X POST "${API_URL}/api/v1/runs/${RUN_ID}/artifacts/${type}/revise" \
    -H "${AUTH}" -H "${CT}" \
    -d "{\"feedback\": \"${feedback}\"}" | python3 -m json.tool
}

cmd_publish() {
  _require_run_id
  echo "==> Publishing approved artifacts..."
  curl -s -X POST "${API_URL}/api/v1/runs/${RUN_ID}/publish" -H "${AUTH}" | python3 -m json.tool
}

cmd_export() {
  _require_run_id
  local outfile="launchkit-${RUN_ID}.zip"
  curl -s "${API_URL}/api/v1/runs/${RUN_ID}/export" -H "${AUTH}" -o "${outfile}"
  echo "Saved: ${outfile}"
}

cmd_metrics() {
  _require_run_id
  curl -s "${API_URL}/api/v1/runs/${RUN_ID}/metrics" -H "${AUTH}" | python3 -m json.tool
}

cmd_poll_metrics() {
  _require_run_id
  curl -s -X POST "${API_URL}/api/v1/runs/${RUN_ID}/metrics/poll" -H "${AUTH}" | python3 -m json.tool
}

cmd_retrospective() {
  _require_run_id
  curl -s -X POST "${API_URL}/api/v1/runs/${RUN_ID}/retrospective/generate" -H "${AUTH}" | python3 -m json.tool
}

cmd_all() {
  cmd_create
  export RUN_ID
  cmd_intel
  cmd_analyze
  cmd_generate
  cmd_artifacts
  echo ""
  echo "==> Pipeline complete. RUN_ID=${RUN_ID}"
  echo "    Next: ./scripts/pipeline.sh approve-all && ./scripts/pipeline.sh publish"
}

# ── Dispatch ──────────────────────────────────────────────────────────────────
COMMAND="${1:-help}"
shift || true

case "${COMMAND}" in
  create|get|intel|intel-start|wait-intel|analyze|generate|artifacts|artifact|approve|approve-all|revise|publish|export|metrics|poll-metrics|retrospective|all)
    _require_secret
    ;;
esac

case "${COMMAND}" in
  help)          cmd_help ;;
  preset)        cmd_preset ;;
  health)        cmd_health ;;
  create)        cmd_create ;;
  get)           cmd_get ;;
  intel)         cmd_intel ;;
  intel-start)   cmd_intel_start ;;
  wait-intel)    cmd_wait_intel ;;
  analyze)       cmd_analyze ;;
  generate)      cmd_generate ;;
  artifacts)     cmd_artifacts ;;
  artifact)      cmd_artifact ;;
  approve)       cmd_approve ;;
  approve-all)   cmd_approve_all ;;
  revise)        cmd_revise ;;
  publish)       cmd_publish ;;
  export)        cmd_export ;;
  metrics)       cmd_metrics ;;
  poll-metrics)  cmd_poll_metrics ;;
  retrospective) cmd_retrospective ;;
  all)           cmd_all ;;
  *)
    echo "Unknown command: ${COMMAND}"
    cmd_help
    exit 1
    ;;
esac
