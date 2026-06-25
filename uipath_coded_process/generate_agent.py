"""LaunchKit Generate — UiPath coded agent proxy for content generation."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

GENERATE_TIMEOUT_SECONDS = 600.0
CONNECT_TIMEOUT_SECONDS = 30.0


def _client() -> httpx.Client:
    timeout = httpx.Timeout(GENERATE_TIMEOUT_SECONDS, connect=CONNECT_TIMEOUT_SECONDS)
    return httpx.Client(timeout=timeout)


def _warmup(client: httpx.Client, base: str) -> None:
    try:
        client.get(f"{base}/health")
    except httpx.HTTPError:
        pass


@dataclass
class GenerateIn:
    run_id: str
    api_url: str
    api_secret: str


@dataclass
class GenerateOut:
    run_id: str
    status: str
    message: str


def generate(input: GenerateIn) -> GenerateOut:
    """Call LaunchKit POST /api/v1/runs/{run_id}/generate after coding-agent analyze."""
    base = input.api_url.rstrip("/")
    url = f"{base}/api/v1/runs/{input.run_id}/generate"
    headers = {"Authorization": f"Bearer {input.api_secret}"}

    with _client() as client:
        _warmup(client, base)
        response = client.post(url, headers=headers)
        response.raise_for_status()
        data = response.json()

    return GenerateOut(
        run_id=str(data.get("run_id", input.run_id)),
        status=str(data.get("status", "")),
        message=str(data.get("message", "")),
    )
