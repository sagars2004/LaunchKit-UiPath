"""API route tests."""

from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from backend.main import app
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert data["checks"]["api"] == "ok"


@pytest.mark.asyncio
async def test_api_routes_require_auth(test_client):
    response = await test_client.post("/api/v1/runs")
    assert response.status_code == 401
    assert "error" in response.json()


@pytest.mark.asyncio
async def test_create_and_get_run(test_client, auth_headers):
    response = await test_client.post(
        "/api/v1/runs",
        headers=auth_headers,
        json={
            "github_url": "https://github.com/tiangolo/fastapi",
            "hackathon_url": "https://devpost.com/hackathons",
            "hackathon_name": "Test Hackathon",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data
    assert data["status"] == "intake"

    run_id = data["run_id"]
    get_resp = await test_client.get(f"/api/v1/runs/{run_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    run_data = get_resp.json()
    assert "github.com/tiangolo/fastapi" in run_data["run"]["intake"]["github_url"]


@pytest.mark.asyncio
async def test_get_run_not_found(test_client, auth_headers):
    response = await test_client.get(
        f"/api/v1/runs/{UUID('00000000-0000-0000-0000-000000000001')}",
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_intel_flow(test_client, auth_headers, load_fixture):
    create = await test_client.post(
        "/api/v1/runs",
        headers=auth_headers,
        json={
            "github_url": "https://github.com/tiangolo/fastapi",
            "hackathon_url": "https://devpost.com/hackathons",
        },
    )
    run_id = create.json()["run_id"]

    with (
        patch("backend.api.routes.runs.HackathonIntelAgent") as mock_intel_cls,
        patch("backend.api.routes.runs.WinnerResearcherAgent") as mock_winner_cls,
        patch("backend.api.routes.runs.generate_winning_brief", new_callable=AsyncMock) as mock_wb,
    ):
        from backend.models.intelligence import HackathonBrief, WinnerPatterns

        mock_intel_cls.return_value.run = AsyncMock(
            return_value=HackathonBrief.model_validate(load_fixture("hackathon_brief.json"))
        )
        mock_winner_cls.return_value.run = AsyncMock(
            return_value=WinnerPatterns(hackathon_name="Test")
        )
        mock_wb.return_value = {"headline_recommendation": "Test brief"}

        resp = await test_client.post(f"/api/v1/runs/{run_id}/intel", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["message"] == "Intelligence gathering complete"


@pytest.mark.asyncio
async def test_intel_async_returns_immediately(test_client, auth_headers, load_fixture):
    create = await test_client.post(
        "/api/v1/runs",
        headers=auth_headers,
        json={
            "github_url": "https://github.com/tiangolo/fastapi",
            "hackathon_url": "https://devpost.com/hackathons",
        },
    )
    run_id = create.json()["run_id"]

    with (
        patch("backend.api.routes.runs.HackathonIntelAgent") as mock_intel_cls,
        patch("backend.api.routes.runs.WinnerResearcherAgent") as mock_winner_cls,
        patch("backend.api.routes.runs.generate_winning_brief", new_callable=AsyncMock) as mock_wb,
    ):
        from backend.models.intelligence import HackathonBrief, WinnerPatterns

        mock_intel_cls.return_value.run = AsyncMock(
            return_value=HackathonBrief.model_validate(load_fixture("hackathon_brief.json"))
        )
        mock_winner_cls.return_value.run = AsyncMock(
            return_value=WinnerPatterns(hackathon_name="Test")
        )
        mock_wb.return_value = {"headline_recommendation": "Test brief"}

        resp = await test_client.post(
            f"/api/v1/runs/{run_id}/intel?async=true",
            headers=auth_headers,
        )
        assert resp.status_code == 202
        assert "started" in resp.json()["message"].lower()

        get_resp = await test_client.get(f"/api/v1/runs/{run_id}", headers=auth_headers)
        assert get_resp.json()["run"]["hackathon_brief"] is not None


@pytest.mark.asyncio
async def test_analyze_requires_intel(test_client, auth_headers):
    create = await test_client.post(
        "/api/v1/runs",
        headers=auth_headers,
        json={
            "github_url": "https://github.com/tiangolo/fastapi",
            "hackathon_url": "https://devpost.com/hackathons",
        },
    )
    run_id = create.json()["run_id"]
    resp = await test_client.post(f"/api/v1/runs/{run_id}/analyze", headers=auth_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_submit_analyze_from_coding_agent(
    test_client, auth_headers, memory_store, load_fixture
):
    create = await test_client.post(
        "/api/v1/runs",
        headers=auth_headers,
        json={
            "github_url": "https://github.com/tiangolo/fastapi",
            "hackathon_url": "https://devpost.com/hackathons",
        },
    )
    run_id = UUID(create.json()["run_id"])
    await memory_store.update_run(
        run_id,
        {"hackathon_brief": load_fixture("hackathon_brief.json")},
    )

    code_intel = load_fixture("code_intelligence.json")
    resp = await test_client.post(
        f"/api/v1/runs/{run_id}/analyze/submit",
        headers=auth_headers,
        json={
            "code_intelligence": code_intel,
            "repo_context": {"owner": "tiangolo", "repo": "fastapi"},
            "coding_tool": "cursor",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["coding_tool"] == "cursor"
    assert "cursor" in data["message"]

    run_resp = await test_client.get(f"/api/v1/runs/{run_id}", headers=auth_headers)
    run = run_resp.json()["run"]
    assert run["code_intelligence"]["project_name"] == code_intel["project_name"]
    assert run["repo_context"]["_launchkit_meta"]["coding_tool"] == "cursor"


@pytest.mark.asyncio
async def test_artifact_approval_flow(test_client, auth_headers, memory_store):
    create = await test_client.post(
        "/api/v1/runs",
        headers=auth_headers,
        json={
            "github_url": "https://github.com/tiangolo/fastapi",
            "hackathon_url": "https://devpost.com/hackathons",
        },
    )
    run_id = UUID(create.json()["run_id"])

    await memory_store.upsert_artifact(run_id, "readme", "# Test README")

    list_resp = await test_client.get(f"/api/v1/runs/{run_id}/artifacts", headers=auth_headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()["artifacts"]) == 1

    approve = await test_client.post(
        f"/api/v1/runs/{run_id}/artifacts/readme/approve", headers=auth_headers
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_revise_artifact(test_client, auth_headers, memory_store, load_fixture):
    create = await test_client.post(
        "/api/v1/runs",
        headers=auth_headers,
        json={
            "github_url": "https://github.com/tiangolo/fastapi",
            "hackathon_url": "https://devpost.com/hackathons",
        },
    )
    run_id = UUID(create.json()["run_id"])
    await memory_store.update_run(
        run_id,
        {
            "hackathon_brief": load_fixture("hackathon_brief.json"),
        },
    )
    await memory_store.upsert_artifact(run_id, "readme", "# Original README")

    with patch("backend.api.routes.artifacts.RevisionAgent") as mock_rev_cls:
        mock_rev_cls.return_value.run = AsyncMock(return_value="# Revised README")

        resp = await test_client.post(
            f"/api/v1/runs/{run_id}/artifacts/readme/revise",
            headers=auth_headers,
            json={"feedback": "Add more technical detail"},
        )
        assert resp.status_code == 200
        assert "Revised" in resp.json()["content"]


@pytest.mark.asyncio
async def test_export_run(test_client, auth_headers, memory_store):
    create = await test_client.post(
        "/api/v1/runs",
        headers=auth_headers,
        json={
            "github_url": "https://github.com/tiangolo/fastapi",
            "hackathon_url": "https://devpost.com/hackathons",
        },
    )
    run_id = create.json()["run_id"]
    await memory_store.upsert_artifact(UUID(run_id), "readme", "# README")

    resp = await test_client.get(f"/api/v1/runs/{run_id}/export", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
