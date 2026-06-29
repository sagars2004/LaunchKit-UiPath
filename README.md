# LaunchKit

> AI-powered hackathon success pipeline — from repo and hackathon URL to judge-ready artifacts.
> UiPath AgentHack 2026. By Sagar Sahu.

## Project Description

### Problem

Hackathon teams spend a disproportionate amount of time on work that is not building the product: decoding judging criteria from event pages, researching past winners, and rewriting readmes, pitches, and social copy across multiple channels. That manual, repetitive work pulls engineers away from shipping code — often late into the night — and strong projects can lose to teams with better documentation, not better software.

### Solution

LaunchKit is a repeatable launch pipeline for hackathon participants. Given a GitHub repository URL and a hackathon event URL, it:

1. **Gathers intel** — scrapes hackathon pages and researches winner patterns to build a structured judging brief.
2. **Analyzes code** — via server-side LLM agents or UiPath **Coded Agents** that invoke external coding CLIs (Cursor, Claude Code, Codex, Gemini CLI).
3. **Generates artifacts** — readme, Devpost copy, demo script, social content, and blog draft, each quality-scored.
4. **Orchestrates end-to-end** — UiPath **Maestro BPMN** coordinates API calls, coded agents, human review, and publish behind a single approval gate.

The result: teams spend more time building and less time on submission paperwork.

## Agent Type

**This solution uses Coded Agents in UiPath only.**

LaunchKit uses a UiPath Coding Agent connected to an external Cursor agent through UiPath SDK. All UiPath agent logic lives in Python coded agents under `uipath_coded_process/`, deployed to UiPath Automation Cloud and invoked by Maestro BPMN at runtime.

| Entry point | File | Role |
|-------------|------|------|
| `main` | `main.py` | Proxies to backend `POST /analyze` (server-side LLM) |
| `analyze_with_coding_agent` | `analyze_with_coding_agent.py` | Clones repo, invokes external coding CLI, submits via `POST /analyze/submit` |
| `generate` | `generate_agent.py` | Proxies to `POST /generate` after analysis |


## UiPath Components

| Component | How LaunchKit uses it |
|-----------|----------------------|
| **Maestro BPMN** | Primary orchestrator — drives the full pipeline: create run → intel → analyze → generate → human review → publish |
| **API Workflows** | HTTP integration steps inside Maestro (`POST /runs`, `/intel`, `/generate`, `/publish`) against the LaunchKit FastAPI backend |
| **Coded Agents** | Python agents (`analyze_with_coding_agent`, `main`, `generate`) deployed from `uipath_coded_process/`; Maestro invokes them at the analyze and generate steps |
| **Studio Web** | Develop, test, and deploy coded agents to Automation Cloud |
| **Orchestrator** | Runs Maestro processes and coded-agent jobs; stores assets (e.g. `LAUNCHKIT_API_SECRET`, API URL) used by workflow steps |
| **Action Center** | Human-in-the-loop approval gate before artifacts are published |
| **UiPath CLI** | Local agent development — `uipath init`, `uipath run` for testing coded agents before deployment |


## Other Technologies

| Category | Tools |
|----------|-------|
| Backend | FastAPI, Uvicorn, Python 3.11+ |
| Database | Supabase (PostgreSQL) — runs, artifacts, revisions, metrics |
| LLM | NVIDIA NIM (default) or Google Gemini |
| Hosting | Render (Docker deployment) |
| External coding CLIs | Cursor, Claude Code, Codex, Gemini CLI |
| Integrations | GitHub (repo source + README publish), Devpost (hackathon context) |

## Features

| Feature | Description |
|---------|-------------|
| Hackathon Intelligence | Extracts judging criteria and event context from hackathon pages |
| Winner Research | Researches past submission patterns to inform artifact generation |
| Code Analysis | Server-side LLM or external coding CLI via UiPath coded agents |
| Artifact Generation | Produces readme, Devpost copy, demo script, social content, and blog draft with quality scores |
| Human Review | Single approval gate in Maestro before publish |
| End-to-End Orchestration | One Maestro workflow from repo URL to publish-ready output |

## Setup Instructions

Follow these steps to configure and run LaunchKit for judging. No secrets are included here — obtain your own keys and never commit them to git.

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or `pip`
- A Supabase project
- An LLM API key — [NVIDIA NIM](https://build.nvidia.com/) (recommended) or [Google Gemini](https://aistudio.google.com/apikey)
- UiPath Automation Cloud access with Maestro, Studio Web, and Orchestrator
- (Optional) GitHub personal access token for README publish
- (Optional) Cursor / Claude Code / Codex / Gemini CLI for the coding-agent analyze path

### Step 1 — Clone and configure environment

```bash
git clone https://github.com/<your-org>/LaunchKit-UiPath.git
cd LaunchKit-UiPath
cp .env.example .env
```

Edit `.env` and set at minimum:

| Variable | Description |
|----------|-------------|
| `LAUNCHKIT_API_SECRET` | Strong random bearer token for all `/api/v1/*` routes |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Supabase service role key (server-side only) |
| `NVIDIA_API_KEY` or `GEMINI_API_KEY` | LLM provider key (see `LLM_PROVIDER` in `.env.example`) |
| `GITHUB_TOKEN` | Optional — required only for README publish |

See `.env.example` for all options and comments.

### Step 2 — Apply Supabase schema

1. Open your Supabase project → **SQL Editor**.
2. Paste and run `infrastructure/supabase/schema.sql`.
3. If you see permission errors from the API, also run `infrastructure/supabase/grants.sql`.

Or run `make db-push` for instructions.

### Step 3 — Start the backend locally

```bash
pip install -r requirements.txt
make dev
```

Verify connectivity:

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
```

Expected: `"status": "healthy"` with Supabase and LLM checks passing.

For production judging, the same FastAPI service can be deployed to Render using `render.yaml` and the Render dashboard. Use your deployed base URL wherever `API_URL` is referenced below.

### Step 4 — Deploy UiPath coded agents

```bash
cd uipath_coded_process
uv sync
uv run uipath init --no-agents-md-override
```

Deploy the coded agents to UiPath Automation Cloud via Studio Web. The project exposes three entry points (see `uipath.json`):

- `main` — server-side analyze proxy
- `analyze_with_coding_agent` — external coding CLI path (**recommended for demo**)
- `generate` — artifact generation proxy

Test locally before deploying:

```bash
uv run uipath run analyze_with_coding_agent '{
  "run_id": "YOUR_RUN_ID",
  "api_url": "http://localhost:8000",
  "api_secret": "YOUR_LAUNCHKIT_API_SECRET",
  "coding_tool": "cursor"
}'
```

Replace placeholders with your run ID and secret. Do not share these values publicly.

More detail: [`uipath_coded_process/README.md`](uipath_coded_process/README.md)

### Step 5 — Configure Maestro BPMN workflow

In UiPath Automation Cloud, configure a Maestro BPMN process with these stages:

| Step | Action |
|------|--------|
| 1. Create Run | API Workflow → `POST {API_URL}/api/v1/runs` with `github_url`, `hackathon_url`, `hackathon_name`, `track_category` |
| 2. Intel | API Workflow → `POST {API_URL}/api/v1/runs/{run_id}/intel?async=true`, then poll `GET /runs/{run_id}` until `status` is `intake` |
| 3. Analyze | Invoke coded agent `analyze_with_coding_agent` (set `coding_tool` to `cursor`, `claude`, `codex`, or `gemini`) |
| 4. Generate | Invoke coded agent `generate` |
| 5. Human review | Action Center / Studio approval task |
| 6. Publish | API Workflow → `POST {API_URL}/api/v1/runs/{run_id}/publish` |

Store `API_URL` and `LAUNCHKIT_API_SECRET` as Orchestrator assets or Maestro variables. Pass `Authorization: Bearer {LAUNCHKIT_API_SECRET}` on every API call.

### Step 6 — Run the demo (for judges)

**Option A — Maestro (recommended):** Trigger the Maestro BPMN process from Studio Web or Orchestrator. Monitor step completion in the Maestro run view. Approve artifacts at the human review gate.

**Option B — CLI smoke test:** From the repo root with `.env` configured:

```bash
chmod +x scripts/pipeline.sh scripts/demo.sh

./scripts/pipeline.sh health
PRESET=uipath ./scripts/pipeline.sh all
./scripts/pipeline.sh artifacts
./scripts/pipeline.sh approve-all
./scripts/pipeline.sh publish
```

This runs create → intel → analyze → generate against the API. For the coding-agent analyze path, run `./scripts/pipeline.sh intel` first, then `./scripts/coding_agent.sh cursor` instead of `./scripts/pipeline.sh analyze`.

Copy/paste reference: [`scripts/PIPELINE_COMMANDS.md`](scripts/PIPELINE_COMMANDS.md)

### Step 7 — Verify output

- **API:** `GET /api/v1/runs/{run_id}/artifacts` — five artifacts with quality scores
- **Supabase:** `runs` and `artifacts` tables populated for the run
- **Maestro:** all workflow steps completed; publish step returns success

## License

MIT — see [LICENSE](LICENSE).
