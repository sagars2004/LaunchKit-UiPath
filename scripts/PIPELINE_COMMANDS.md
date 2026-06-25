# LaunchKit Pipeline — Copy/Paste Commands

Prerequisites: server running (`make dev`), `.env` configured.

The script **auto-loads `.env`** (including `RUN_ID`). You can also run curls manually:

```bash
cd /path/to/LaunchKit-UiPath
set -a && source .env && set +a   # exports RUN_ID, LAUNCHKIT_API_SECRET, etc.
export AUTH="Authorization: Bearer $LAUNCHKIT_API_SECRET"
export API_URL="${API_URL:-http://localhost:8000}"
```

Or just use `./scripts/pipeline.sh` — no manual exports needed.

---

## Test case presets

| Preset | GitHub repo | Hackathon |
|--------|-------------|-----------|
| `fastapi` | github.com/tiangolo/fastapi | devpost.com/hackathons |
| `uipath` | github.com/tiangolo/fastapi | uipath-agenthack.devpost.com |
| `custom` | Set `GITHUB_URL` + `HACKATHON_URL` yourself |

```bash
PRESET=uipath ./scripts/pipeline.sh create
PRESET=custom GITHUB_URL=https://github.com/you/repo HACKATHON_URL=https://... ./scripts/pipeline.sh create
```

---

## Health check

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
```

---

## Create run

```bash
curl -X POST "$API_URL/api/v1/runs" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{
    "github_url": "https://github.com/tiangolo/fastapi",
    "hackathon_url": "https://uipath-agenthack.devpost.com/",
    "hackathon_name": "UiPath AgentHack",
    "track_category": "Maestro BPMN"
  }' | python3 -m json.tool

# Save the run_id:
export RUN_ID="paste-run-id-here"
```

---

## Step 1 — Intelligence (`/intel`)

```bash
curl -X POST "$API_URL/api/v1/runs/$RUN_ID/intel" \
  -H "$AUTH" | python3 -m json.tool
```

---

## Step 2 — Code analysis (`/analyze`)

**Backend path** (Gemini/NVIDIA on server):

```bash
curl -X POST "$API_URL/api/v1/runs/$RUN_ID/analyze" \
  -H "$AUTH" | python3 -m json.tool
```

**Coding agent path** (Claude Code, Cursor, Codex, Gemini CLI via UiPath Maestro):

```bash
# From uipath_coded_process/ after intel completes:
uv run uipath run analyze_with_coding_agent "{
  \"run_id\": \"$RUN_ID\",
  \"api_url\": \"$API_URL\",
  \"api_secret\": \"$LAUNCHKIT_API_SECRET\",
  \"coding_tool\": \"claude\"
}"
```

Or submit pre-computed analysis directly:

```bash
curl -X POST "$API_URL/api/v1/runs/$RUN_ID/analyze/submit" \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{"code_intelligence": {...}, "coding_tool": "cursor"}' \
  | python3 -m json.tool
```

---

## Step 3 — Generate artifacts (`/generate`)

Takes 1–3 minutes (multiple LLM calls).

```bash
curl -X POST "$API_URL/api/v1/runs/$RUN_ID/generate" \
  -H "$AUTH" | python3 -m json.tool
```

---

## Review artifacts

List all:

```bash
curl -s "$API_URL/api/v1/runs/$RUN_ID/artifacts" \
  -H "$AUTH" | python3 -m json.tool
```

Single artifact (`readme`, `devpost_copy`, `demo_script`, `social_content`, `blog_draft`):

```bash
curl -s "$API_URL/api/v1/runs/$RUN_ID/artifacts/readme" \
  -H "$AUTH" | python3 -m json.tool
```

Full run state:

```bash
curl -s "$API_URL/api/v1/runs/$RUN_ID" \
  -H "$AUTH" | python3 -m json.tool
```

---

## Approve artifacts

```bash
curl -X POST "$API_URL/api/v1/runs/$RUN_ID/artifacts/readme/approve" -H "$AUTH"
curl -X POST "$API_URL/api/v1/runs/$RUN_ID/artifacts/devpost_copy/approve" -H "$AUTH"
curl -X POST "$API_URL/api/v1/runs/$RUN_ID/artifacts/demo_script/approve" -H "$AUTH"
curl -X POST "$API_URL/api/v1/runs/$RUN_ID/artifacts/social_content/approve" -H "$AUTH"
curl -X POST "$API_URL/api/v1/runs/$RUN_ID/artifacts/blog_draft/approve" -H "$AUTH"
```

---

## Revise an artifact

```bash
curl -X POST "$API_URL/api/v1/runs/$RUN_ID/artifacts/devpost_copy/revise" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"feedback": "Lead with UiPath Maestro BPMN. Add a concrete time-saved metric."}' \
  | python3 -m json.tool
```

---

## Publish approved artifacts

Requires `GITHUB_TOKEN` in `.env` for README push.

```bash
curl -X POST "$API_URL/api/v1/runs/$RUN_ID/publish" \
  -H "$AUTH" | python3 -m json.tool
```

---

## Export zip

```bash
curl -s "$API_URL/api/v1/runs/$RUN_ID/export" \
  -H "$AUTH" -o "launchkit-$RUN_ID.zip"
```

---

## Analytics (optional)

```bash
curl -X POST "$API_URL/api/v1/runs/$RUN_ID/metrics/poll" -H "$AUTH" | python3 -m json.tool
curl -s "$API_URL/api/v1/runs/$RUN_ID/metrics" -H "$AUTH" | python3 -m json.tool
curl -X POST "$API_URL/api/v1/runs/$RUN_ID/retrospective/generate" -H "$AUTH" | python3 -m json.tool
```

---

## Script shortcut (recommended — reads RUN_ID from .env automatically)

```bash
chmod +x scripts/pipeline.sh

./scripts/pipeline.sh help
./scripts/pipeline.sh health
./scripts/pipeline.sh analyze      # uses RUN_ID from .env
./scripts/pipeline.sh generate
./scripts/pipeline.sh artifacts
./scripts/pipeline.sh approve-all
./scripts/pipeline.sh publish
./scripts/pipeline.sh export

# Full pipeline in one go:
PRESET=uipath ./scripts/pipeline.sh all
```
