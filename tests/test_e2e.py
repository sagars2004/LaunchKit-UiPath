"""End-to-end integration test — requires INTEGRATION=true and live API keys."""

import os

import pytest

INTEGRATION = os.getenv("INTEGRATION", "").lower() == "true"


@pytest.mark.integration
@pytest.mark.skipif(not INTEGRATION, reason="Set INTEGRATION=true to run E2E tests")
@pytest.mark.asyncio
async def test_full_pipeline_e2e():
    """
    Full pipeline against live services.
    Demo repo: replace with your project repo before running.
    """
    from backend.config import get_settings
    from backend.main import app
    from httpx import ASGITransport, AsyncClient

    settings = get_settings()
    headers = {"Authorization": f"Bearer {settings.launchkit_api_secret}"}

    demo_repo = os.getenv("DEMO_REPO", "https://github.com/tiangolo/fastapi")
    demo_hackathon = os.getenv("DEMO_HACKATHON", "https://devpost.com/hackathons")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create = await client.post(
            "/api/v1/runs",
            headers=headers,
            json={
                "github_url": demo_repo,
                "hackathon_url": demo_hackathon,
                "hackathon_name": "UiPath AgentHack",
                "track_category": "Maestro BPMN",
            },
        )
        assert create.status_code == 200
        run_id = create.json()["run_id"]

        intel = await client.post(f"/api/v1/runs/{run_id}/intel", headers=headers)
        assert intel.status_code == 200

        analyze = await client.post(f"/api/v1/runs/{run_id}/analyze", headers=headers)
        assert analyze.status_code == 200

        generate = await client.post(f"/api/v1/runs/{run_id}/generate", headers=headers)
        assert generate.status_code == 200
        assert generate.json()["status"] == "reviewing"

        artifacts = await client.get(f"/api/v1/runs/{run_id}/artifacts", headers=headers)
        assert artifacts.status_code == 200
        assert len(artifacts.json()["artifacts"]) >= 1
