"""
LaunchKit Coding Analyze — UiPath Coded Agent reference.

Maestro invokes the deployed agent at:
  uipath_coded_process/analyze_with_coding_agent.py

Flow:
  1. GET /api/v1/runs/{run_id} — fetch github_url + hackathon_brief
  2. Clone repo (or use repo_path)
  3. Invoke coding_tool CLI (claude | cursor | codex | gemini)
  4. POST /api/v1/runs/{run_id}/analyze/submit — store CodeIntelligence
"""

from __future__ import annotations

import httpx

CODING_TOOLS = ("claude", "cursor", "codex", "gemini")
ANALYZE_TIMEOUT_SECONDS = 300.0


async def execute(
    api_url: str,
    api_secret: str,
    run_id: str,
    coding_tool: str = "claude",
    repo_path: str = "",
) -> dict:
    """Thin reference — production implementation is analyze_with_coding_agent.py."""
    base = api_url.rstrip("/")
    headers = {"Authorization": f"Bearer {api_secret}"}

    async with httpx.AsyncClient(timeout=ANALYZE_TIMEOUT_SECONDS) as client:
        run_resp = await client.get(f"{base}/api/v1/runs/{run_id}", headers=headers)
        run_resp.raise_for_status()
        run = run_resp.json()["run"]

        if not run.get("hackathon_brief"):
            raise ValueError("Run intel required before coding-agent analyze")

        # In Studio Web: call analyze_with_coding_agent coded function instead of this stub.
        submit_resp = await client.post(
            f"{base}/api/v1/runs/{run_id}/analyze/submit",
            headers=headers,
            json={
                "code_intelligence": {},
                "repo_context": {"repo_path": repo_path or run["intake"]["github_url"]},
                "coding_tool": coding_tool,
            },
        )
        submit_resp.raise_for_status()
        return submit_resp.json()
