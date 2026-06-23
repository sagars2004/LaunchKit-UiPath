"""
LaunchKit FastAPI application entry point.

Provides:
- Lifespan management (startup/shutdown)
- CORS middleware
- Bearer token auth on /api/v1/* routes
- Request logging middleware
- Global exception handlers
- /health endpoint (Supabase + Gemini connectivity)
"""

import logging
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import analytics, artifacts, runs
from backend.config import Settings, get_settings
from backend.core.exceptions import register_exception_handlers
from backend.core.logging import RequestLoggingMiddleware, configure_logging

logger = logging.getLogger("launchkit")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.environment)
    logger.info("LaunchKit starting (env=%s)", settings.environment)
    if not settings.launchkit_api_secret:
        logger.warning("LAUNCHKIT_API_SECRET is not set — /api/v1 routes will reject all requests")
    app.state.settings = settings
    yield
    logger.info("LaunchKit shutting down")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="LaunchKit",
        description="AI-powered hackathon success pipeline",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.is_development else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)

    register_exception_handlers(app)

    api_prefix = settings.api_v1_prefix
    app.include_router(runs.router, prefix=api_prefix)
    app.include_router(artifacts.router, prefix=api_prefix)
    app.include_router(analytics.router, prefix=api_prefix)

    @app.get("/health", tags=["health"])
    async def health_check() -> dict[str, Any]:
        """Check API, Supabase, and Gemini connectivity."""
        checks: dict[str, Any] = {
            "api": "ok",
            "supabase": await _check_supabase(settings),
            "llm": await _check_llm(settings),
        }
        all_ok = all(
            v == "ok" or (isinstance(v, dict) and v.get("status") == "ok") for v in checks.values()
        )
        return {
            "status": "healthy" if all_ok else "degraded",
            "environment": settings.environment,
            "checks": checks,
        }

    return app


async def _check_supabase(settings: Settings) -> dict[str, str]:
    if not settings.supabase_url or not settings.supabase_service_key:
        return {"status": "unconfigured", "detail": "SUPABASE_URL or SUPABASE_SERVICE_KEY missing"}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{settings.supabase_url.rstrip('/')}/rest/v1/",
                headers={
                    "apikey": settings.supabase_service_key,
                    "Authorization": f"Bearer {settings.supabase_service_key}",
                },
            )
            if response.status_code < 500:
                return {"status": "ok"}
            return {"status": "error", "detail": f"HTTP {response.status_code}"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


async def _check_llm(settings: Settings) -> dict[str, str]:
    provider = settings.resolved_llm_provider
    if provider == "nvidia":
        return await _check_nvidia(settings)
    return await _check_gemini(settings)


async def _check_nvidia(settings: Settings) -> dict[str, str]:
    if not settings.nvidia_api_key:
        return {"status": "unconfigured", "detail": "NVIDIA_API_KEY missing"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{settings.nvidia_base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.nvidia_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.nvidia_model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 5,
                },
            )
            if response.status_code == 200:
                return {"status": "ok", "provider": "nvidia", "model": settings.nvidia_model}
            return {
                "status": "error",
                "provider": "nvidia",
                "detail": f"HTTP {response.status_code}: {response.text[:200]}",
            }
    except Exception as exc:
        return {"status": "error", "provider": "nvidia", "detail": str(exc)}


async def _check_gemini(settings: Settings) -> dict[str, str]:
    if not settings.gemini_api_key:
        return {"status": "unconfigured", "detail": "GEMINI_API_KEY missing (LLM_PROVIDER=gemini)"}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                params={"key": settings.gemini_api_key},
            )
            if response.status_code == 200:
                return {
                    "status": "ok",
                    "provider": "gemini",
                    "model": settings.gemini_model,
                }
            return {
                "status": "error",
                "provider": "gemini",
                "detail": f"HTTP {response.status_code}",
            }
    except Exception as exc:
        return {"status": "error", "provider": "gemini", "detail": str(exc)}


app = create_app()
