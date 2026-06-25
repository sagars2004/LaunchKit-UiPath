# LaunchKit UiPath Coded Agents

UiPath coded agents for the LaunchKit hackathon pipeline. Maestro orchestrates these agents to earn **Coding Agents** bonus points (Claude Code, Cursor, Codex, Gemini CLI).

## Agents

| Entry point | File | Purpose |
|-------------|------|---------|
| `main` | `main.py` | Proxy to backend `POST /analyze` (Gemini on server) |
| `analyze_with_coding_agent` | `analyze_with_coding_agent.py` | **Bonus path** — clones repo, invokes external coding CLI, submits via `POST /analyze/submit` |
| `generate` | `generate_agent.py` | Proxy to `POST /generate` after analysis |

## Maestro flow (recommended)

1. **Create Run** — HTTP `POST /api/v1/runs`
2. **Intel** — HTTP `POST /api/v1/runs/{id}/intel?async=true`, poll until `intake`
3. **Analyze (coding agent)** — invoke `analyze_with_coding_agent` with `coding_tool`
4. **Generate** — invoke `generate`
5. **Human review** — Action Center / Studio approval
6. **Publish** — HTTP `POST /api/v1/runs/{id}/publish`

## Coding agent analyze

```bash
cd uipath_coded_process
uv run uipath run analyze_with_coding_agent '{
  "run_id": "YOUR_RUN_ID",
  "api_url": "https://launchkit-uipath.onrender.com",
  "api_secret": "YOUR_SECRET",
  "coding_tool": "claude",
  "repo_path": ""
}'
```

### Inputs

| Field | Required | Description |
|-------|----------|-------------|
| `run_id` | Yes | LaunchKit run UUID |
| `api_url` | Yes | LaunchKit API base URL |
| `api_secret` | Yes | `LAUNCHKIT_API_SECRET` bearer token |
| `coding_tool` | No | `cursor` (default), `claude`, `codex`, or `gemini` |
| `repo_path` | No | Local clone path; if empty, shallow-clones from run's `github_url` |
| `work_dir` | No | Directory for git clone when `repo_path` is empty |

### Supported CLIs

| Tool | Default command | Override env var |
|------|-----------------|------------------|
| Claude Code | `claude -p "{prompt}" --output-format text` | `LAUNCHKIT_CLAUDE_CMD` |
| Cursor | `agent -p --trust --output-format json "{prompt}"` | `LAUNCHKIT_CURSOR_CMD` |
| Codex | `codex exec --full-auto "{prompt}"` | `LAUNCHKIT_CODEX_CMD` |
| Gemini CLI | `gemini -p "{prompt}"` | `LAUNCHKIT_GEMINI_CMD` |

Custom commands support `{prompt}` and `{repo_path}` placeholders.

## Local development

**Important:** `uipath.json` lives in this folder. Always run from `uipath_coded_process/` (or use `./scripts/coding_agent.sh` from repo root).

```bash
cd uipath_coded_process
uv sync
uv run uipath init --no-agents-md-override
uv run uipath run analyze_with_coding_agent '{
  "run_id": "YOUR_RUN_ID",
  "api_url": "https://launchkit-uipath.onrender.com",
  "api_secret": "YOUR_LAUNCHKIT_API_SECRET",
  "coding_tool": "claude"
}'
```

From repo root (uses `RUN_ID`, `API_URL`, `LAUNCHKIT_API_SECRET` from `.env`):

```bash
./scripts/pipeline.sh intel          # required before analyze
./scripts/coding_agent.sh claude     # or cursor | codex | gemini
```

Use the same `api_url` where the run was created (Render vs `localhost:8000`).

## Backend endpoint

Coding agents submit structured analysis to:

```
POST /api/v1/runs/{run_id}/analyze/submit
Authorization: Bearer {LAUNCHKIT_API_SECRET}

{
  "code_intelligence": { ... },
  "repo_context": { ... },
  "coding_tool": "claude"
}
```

## Demo tip for judges

Run `analyze_with_coding_agent` against **this repo** with `coding_tool: "cursor"` so LaunchKit analyzes itself using Cursor, then generates Devpost copy that documents the coding-agent orchestration.

**Full step-by-step guide:** [docs/UIPATH_CURSOR_SETUP.md](../docs/UIPATH_CURSOR_SETUP.md)
