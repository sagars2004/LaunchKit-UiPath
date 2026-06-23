"""Analytics and retrospective API routes."""

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends

from backend.agents.retrospective_agent import RetrospectiveAgent
from backend.api.deps import get_store, verify_api_token
from backend.core.exceptions import AgentError
from backend.models.schemas import ActionResponse, MetricsResponse, RetrospectiveResponse
from backend.services.artifact_store import ArtifactStore
from backend.services.github_service import get_github_service

logger = logging.getLogger("launchkit.routes.analytics")

router = APIRouter(prefix="/runs", tags=["analytics"], dependencies=[Depends(verify_api_token)])


@router.get("/{run_id}/metrics", response_model=MetricsResponse)
async def get_metrics(
    run_id: UUID,
    store: ArtifactStore = Depends(get_store),
) -> MetricsResponse:
    """Return all metrics for a run."""
    await store.get_run(run_id)
    metrics = await store.get_metrics(run_id)
    return MetricsResponse(run_id=run_id, metrics=metrics)


@router.post("/{run_id}/metrics/poll", response_model=ActionResponse)
async def poll_metrics(
    run_id: UUID,
    store: ArtifactStore = Depends(get_store),
) -> ActionResponse:
    """Manually trigger metrics collection from GitHub (and placeholder Devpost)."""
    run = await store.get_run(run_id)
    github_svc = get_github_service()

    try:
        stats = await github_svc.get_traffic_stats(run.intake.github_url)
        await store.record_metric(run_id, "github", "stars", stats.get("stars", 0))
        await store.record_metric(run_id, "github", "forks", stats.get("forks", 0))
        if stats.get("views_last_14_days") is not None:
            await store.record_metric(run_id, "github", "views", stats["views_last_14_days"])

        analytics = run.analytics.model_dump()
        analytics["last_polled"] = datetime.now(UTC).isoformat()
        analytics["github_stars"] = stats.get("stars", 0)
        await store.update_run(run_id, {"analytics": analytics})

        return ActionResponse(
            run_id=run_id,
            status=run.status,
            message="Metrics polled successfully",
        )
    except Exception as exc:
        raise AgentError("Metrics polling failed", str(exc)) from exc


@router.get("/{run_id}/retrospective", response_model=RetrospectiveResponse)
async def get_retrospective(
    run_id: UUID,
    store: ArtifactStore = Depends(get_store),
) -> RetrospectiveResponse:
    """Return retrospective report if generated."""
    retrospective = await store.get_retrospective(run_id)
    if not retrospective:
        return RetrospectiveResponse(
            run_id=run_id,
            retrospective=None,
            message="No retrospective generated yet",
        )
    return RetrospectiveResponse(run_id=run_id, retrospective=retrospective)


@router.post("/{run_id}/retrospective/generate", response_model=RetrospectiveResponse)
async def generate_retrospective(
    run_id: UUID,
    store: ArtifactStore = Depends(get_store),
) -> RetrospectiveResponse:
    """Generate retrospective report from metrics and artifacts."""
    run = await store.get_run(run_id)
    metrics = await store.get_metrics(run_id)
    artifacts = await store.list_artifacts(run_id)

    summary = json.dumps(
        [{"type": a.artifact_type.value, "score": a.quality_score} for a in artifacts],
        indent=2,
    )

    agent = RetrospectiveAgent()
    try:
        content = await agent.run(
            metrics_history=[m.model_dump() for m in metrics],
            hackathon_brief=run.hackathon_brief or {},
            artifacts_summary=summary,
        )
    except Exception as exc:
        raise AgentError("Retrospective generation failed", str(exc)) from exc

    retrospective = await store.save_retrospective(run_id, content)
    return RetrospectiveResponse(run_id=run_id, retrospective=retrospective)
