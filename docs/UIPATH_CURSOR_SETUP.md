# LaunchKit + Cursor + UiPath — Step-by-Step Guide

Use this guide after you commit/push the coding-agent code. It walks you through testing with **Cursor CLI** locally, then deploying to **UiPath Cloud** and wiring **Maestro**.

---

## Overview

```
You (terminal)          UiPath Cloud              LaunchKit API (Render)
     │                        │                            │
     │  uipath push/deploy     │                            │
     ├───────────────────────►│                            │
     │                        │  Maestro BPMN              │
     │                        ├─ HTTP create run ─────────►│
     │                        ├─ HTTP intel ──────────────►│
     │                        ├─ coded agent analyze ──────┼──► GET run
     │                        │       │                    │    clone repo
     │                        │       └─ Cursor `agent`  │    POST analyze/submit
     │                        ├─ coded agent generate ────►│
     │                        └─ HTTP publish ────────────►│
```

**Yes, you can use Cursor** — set `"coding_tool": "cursor"` (this is now the default).

---

## Part 1 — One-time setup on your Mac

### 1. Install Cursor CLI

```bash
curl https://cursor.com/install -fsS | bash
```

Verify:

```bash
agent --version
# or: cursor-agent --version
```

### 2. Authenticate Cursor (required for headless/scripts)

**Option A — login (interactive):**

```bash
agent login
agent status    # should show your account
```

**Option B — API key (for CI / unattended):**

1. Get a key from [Cursor Dashboard](https://cursor.com/settings)
2. Add to your root `.env`:

```bash
CURSOR_API_KEY=your_key_here
```

### 3. Install git (for repo clone)

The coding agent shallow-clones the target GitHub repo. `git` must be on PATH (macOS usually has it).

---

## Part 2 — Commit and push your code

```bash
cd /Users/sagarsahu/Desktop/Projects/LaunchKit-UiPath
git add .
git commit -m "Add UiPath coding agent with Cursor CLI support"
git push
```

Render will redeploy the backend if connected to your repo (wait ~2 min for deploy to finish).

---

## Part 3 — Configure environment variables

### Root `.env` (for pipeline scripts)

```bash
API_URL=https://launchkit-uipath.onrender.com
LAUNCHKIT_API_SECRET=your_render_secret    # same as Render env var
RUN_ID=                                    # filled by pipeline.sh create

# Optional — only if using agent login fails in scripts
CURSOR_API_KEY=your_cursor_key
```

### `uipath_coded_process/.env` (for UiPath Cloud deploy)

You already have these — keep them:

```bash
UIPATH_ACCESS_TOKEN=...
UIPATH_URL=https://cloud.uipath.com/yourorg/DefaultTenant
UIPATH_TENANT_ID=...
UIPATH_ORGANIZATION_ID=...
UIPATH_PROJECT_ID=...
```

**Do not** paste shell commands into `.env` files — only `KEY=value` lines.

---

## Part 4 — Test locally BEFORE UiPath (do this first)

Run these from the **repo root** in order.

### Step 4.1 — Health check

```bash
./scripts/pipeline.sh health
```

Should show API + Supabase + LLM ok.

### Step 4.2 — Create a run

```bash
PRESET=uipath ./scripts/pipeline.sh create
```

This prints a `RUN_ID` and saves it to `.env`.

### Step 4.3 — Intel (required before analyze)

```bash
./scripts/pipeline.sh intel
```

Takes 1–3 minutes. Wait until it says intelligence complete.

### Step 4.4 — Run Cursor coding agent analyze

```bash
./scripts/coding_agent.sh cursor
```

What happens internally:

1. Fetches run from `GET /api/v1/runs/{RUN_ID}`
2. Clones the GitHub repo from the run
3. Runs `agent -p --output-format json "<analysis prompt>"` in the repo folder
4. Submits JSON to `POST /api/v1/runs/{RUN_ID}/analyze/submit`

**If it fails:**

| Error | Fix |
|-------|-----|
| `Connection refused` | Use `API_URL=https://launchkit-uipath.onrender.com`, not localhost |
| `401 Unauthorized` | `LAUNCHKIT_API_SECRET` must match Render |
| `agent not found on PATH` | Run Part 1 Cursor CLI install |
| `Run intel required` | Run `./scripts/pipeline.sh intel` first |
| `cursor failed` / auth | Run `agent login` or set `CURSOR_API_KEY` |

### Step 4.5 — Generate artifacts

```bash
./scripts/pipeline.sh generate
```

### Step 4.6 — Verify in API

```bash
./scripts/pipeline.sh artifacts
```

You should see readme, devpost_copy, etc. The run's `repo_context._launchkit_meta.coding_tool` should be `"cursor"`.

---

## Part 5 — Push coded agents to UiPath Cloud

```bash
cd uipath_coded_process
uv sync
uv run uipath init --no-agents-md-override   # regenerate schemas after code changes
uv run uipath push --overwrite             # upload to Studio Web project
```

Optional — publish package to feed:

```bash
uv run uipath deploy --my-workspace
```

### Verify in Studio Web

1. Open [UiPath Cloud](https://cloud.uipath.com) → **Studio Web**
2. Open project **launchkit-analyze** (or your project name)
3. Confirm these entry points exist:
   - `analyze_with_coding_agent`
   - `generate`
   - `main`

---

## Part 6 — Test in UiPath Studio Web

### Test the coding agent entry point

In Studio Web, run/test `analyze_with_coding_agent` with this input JSON:

```json
{
  "run_id": "YOUR_RUN_ID_FROM_STEP_4",
  "api_url": "https://launchkit-uipath.onrender.com",
  "api_secret": "YOUR_LAUNCHKIT_API_SECRET",
  "coding_tool": "cursor"
}
```

**Important:** UiPath Cloud's serverless runtime may **not** have the Cursor `agent` CLI installed. If Studio Web test fails with `agent not found`:

- **For the hackathon demo video:** run `./scripts/coding_agent.sh cursor` locally (Part 4) — judges see Cursor + UiPath coded agent code + Maestro orchestration
- **For Maestro on a robot:** install Cursor CLI on the **robot machine** and set `CURSOR_API_KEY` as an Orchestrator asset/env var

### Test generate entry point

After analyze succeeds:

```json
{
  "run_id": "YOUR_RUN_ID",
  "api_url": "https://launchkit-uipath.onrender.com",
  "api_secret": "YOUR_LAUNCHKIT_API_SECRET"
}
```

Invoke `generate`.

---

## Part 7 — Wire Maestro BPMN

In **Maestro**, create a process with these steps:

| # | Step type | What it does |
|---|-----------|--------------|
| 1 | HTTP Request | `POST {API_URL}/api/v1/runs` → save `run_id` |
| 2 | HTTP Request | `POST {API_URL}/api/v1/runs/{run_id}/intel?async=true` |
| 3 | Wait / Poll | `GET {API_URL}/api/v1/runs/{run_id}` until `hackathon_brief` exists |
| 4 | **Invoke Coded Agent** | `analyze_with_coding_agent` with `coding_tool: cursor` |
| 5 | **Invoke Coded Agent** | `generate` |
| 6 | Human Task | Review artifacts in LaunchKit / Action Center |
| 7 | HTTP Request | `POST {API_URL}/api/v1/runs/{run_id}/publish` |

Store `api_url`, `api_secret`, and `run_id` in Maestro process variables or Orchestrator assets.

---

## Quick reference commands

```bash
# Full local test with Cursor
PRESET=uipath ./scripts/pipeline.sh create
./scripts/pipeline.sh intel
./scripts/coding_agent.sh cursor
./scripts/pipeline.sh generate
./scripts/pipeline.sh artifacts

# Deploy to UiPath
cd uipath_coded_process && uv run uipath push --overwrite

# Manual run (from uipath_coded_process/)
uv run uipath run analyze_with_coding_agent '{
  "run_id": "...",
  "api_url": "https://launchkit-uipath.onrender.com",
  "api_secret": "...",
  "coding_tool": "cursor"
}'
```

---

## Hackathon demo script (2 minutes)

1. Show Maestro BPMN diagram with coded agent steps
2. Run `./scripts/coding_agent.sh cursor` in terminal — point out `agent` analyzing the repo
3. Show `GET /runs/{id}` — `coding_tool: cursor` in metadata
4. Show generated Devpost copy mentioning Cursor + Maestro + UiPath coded agents
