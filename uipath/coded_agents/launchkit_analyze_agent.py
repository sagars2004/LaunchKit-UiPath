"""
LaunchKit Code Analyzer — UiPath Coded Agent reference.

Copy this logic into a UiPath Coded Agent in Studio Web (Python).
Wire Maestro to invoke the agent instead of the API Workflow analyze step.

Inputs (map from Maestro / Orchestrator assets):
  api_url:    https://launchkit-uipath.onrender.com
  api_secret: LAUNCHKIT_API_SECRET
  run_id:     UUID from Create Run step

Output: LaunchKit analyze response JSON (run_id, status, message).
"""

from __future__ import annotations

import httpx

ANALYZE_TIMEOUT_SECONDS = 180.0


async def execute(api_url: str, api_secret: str, run_id: str) -> dict:
    """Call LaunchKit POST /api/v1/runs/{run_id}/analyze."""
    base = api_url.rstrip("/")
    url = f"{base}/api/v1/runs/{run_id}/analyze"
    headers = {"Authorization": f"Bearer {api_secret}"}

    async with httpx.AsyncClient(timeout=ANALYZE_TIMEOUT_SECONDS) as client:
        response = await client.post(url, headers=headers)
        response.raise_for_status()
        return response.json()
