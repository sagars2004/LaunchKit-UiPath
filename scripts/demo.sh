#!/usr/bin/env bash
# LaunchKit demo — full pipeline smoke test via curl
set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
SECRET="${LAUNCHKIT_API_SECRET:-}"
DEMO_REPO="${DEMO_REPO:-https://github.com/tiangolo/fastapi}"
DEMO_HACKATHON="${DEMO_HACKATHON:-https://devpost.com/hackathons}"

AUTH="Authorization: Bearer ${SECRET}"
CT="Content-Type: application/json"

# Check LLM + Supabase credentials
if [[ -n "${NVIDIA_API_KEY:-}" ]] || [[ "${LLM_PROVIDER:-}" == "nvidia" ]]; then
  required_vars=(NVIDIA_API_KEY SUPABASE_URL SUPABASE_SERVICE_KEY LAUNCHKIT_API_SECRET)
elif [[ -n "${GEMINI_API_KEY:-}" ]] || [[ "${LLM_PROVIDER:-}" == "gemini" ]]; then
  required_vars=(GEMINI_API_KEY SUPABASE_URL SUPABASE_SERVICE_KEY LAUNCHKIT_API_SECRET)
else
  required_vars=(NVIDIA_API_KEY SUPABASE_URL SUPABASE_SERVICE_KEY LAUNCHKIT_API_SECRET)
fi
for var in "${required_vars[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    echo "ERROR: $var is not set. Copy .env.example to .env and fill in values."
    exit 1
  fi
done

echo "==> Checking health..."
curl -sf "${API_URL}/health" | python3 -m json.tool

echo ""
echo "==> Starting server check (expect server already running on ${API_URL})..."
if ! curl -sf "${API_URL}/health" > /dev/null; then
  echo "Start the server first: make dev"
  exit 1
fi

echo ""
echo "==> Creating run..."
RUN_RESP=$(curl -sf -X POST "${API_URL}/api/v1/runs" \
  -H "${AUTH}" -H "${CT}" \
  -d "{\"github_url\":\"${DEMO_REPO}\",\"hackathon_url\":\"${DEMO_HACKATHON}\",\"hackathon_name\":\"UiPath AgentHack\",\"track_category\":\"Maestro BPMN\"}")

RUN_ID=$(echo "$RUN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['run_id'])")
echo "Run ID: ${RUN_ID}"

echo ""
echo "==> Act I: Intelligence gathering..."
curl -sf -X POST "${API_URL}/api/v1/runs/${RUN_ID}/intel" -H "${AUTH}" | python3 -m json.tool

echo ""
echo "==> Act II: Code analysis..."
curl -sf -X POST "${API_URL}/api/v1/runs/${RUN_ID}/analyze" -H "${AUTH}" | python3 -m json.tool

echo ""
echo "==> Act II: Content generation + scoring..."
curl -sf -X POST "${API_URL}/api/v1/runs/${RUN_ID}/generate" -H "${AUTH}" | python3 -m json.tool

echo ""
echo "==> Polling until status == reviewing..."
for i in $(seq 1 60); do
  STATUS=$(curl -sf "${API_URL}/api/v1/runs/${RUN_ID}" -H "${AUTH}" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['run']['status'])")
  echo "  [${i}] status=${STATUS}"
  if [[ "$STATUS" == "reviewing" ]]; then
    break
  fi
  if [[ "$STATUS" == "failed" ]]; then
    echo "Pipeline failed!"
    curl -sf "${API_URL}/api/v1/runs/${RUN_ID}" -H "${AUTH}" | python3 -m json.tool
    exit 1
  fi
  sleep 5
done

echo ""
echo "==> Generated artifacts:"
curl -sf "${API_URL}/api/v1/runs/${RUN_ID}/artifacts" -H "${AUTH}" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
for a in data.get('artifacts', []):
    print(f\"--- {a['artifact_type']} (score: {a.get('quality_score', 'N/A')}) ---\")
    content = a.get('content') or ''
    print(content[:500])
    if len(content) > 500:
        print('...[truncated]')
    print()
"

echo ""
echo "==> Demo complete. Run ID: ${RUN_ID}"
