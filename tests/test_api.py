"""API route tests — STEP 1 smoke tests."""

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_endpoint(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ("healthy", "degraded")
    assert "checks" in data
    assert data["checks"]["api"] == "ok"


@pytest.mark.asyncio
async def test_api_routes_require_auth(client):
    response = await client.post("/api/v1/runs")
    assert response.status_code == 401
    data = response.json()
    assert "error" in data


@pytest.mark.asyncio
async def test_api_routes_with_valid_token(client, monkeypatch):
    from backend.config import get_settings

    settings = get_settings()
    response = await client.post(
        "/api/v1/runs",
        headers={"Authorization": f"Bearer {settings.launchkit_api_secret}"},
    )
    assert response.status_code == 200
