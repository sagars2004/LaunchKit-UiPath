"""
LaunchKit Generate — UiPath Coded Agent reference.

Invoke after analyze (backend or coding-agent path) to generate Devpost-ready artifacts.
"""

from __future__ import annotations

import httpx

GENERATE_TIMEOUT_SECONDS = 600.0


async def execute(api_url: str, api_secret: str, run_id: str) -> dict:
    base = api_url.rstrip("/")
    url = f"{base}/api/v1/runs/{run_id}/generate"
    headers = {"Authorization": f"Bearer {api_secret}"}

    async with httpx.AsyncClient(timeout=GENERATE_TIMEOUT_SECONDS) as client:
        response = await client.post(url, headers=headers)
        response.raise_for_status()
        return response.json()
