"""Analytics and retrospective API routes — STEP 7 implementation pending."""

from fastapi import APIRouter, Depends

from backend.api.deps import verify_api_token

router = APIRouter(prefix="/runs", tags=["analytics"], dependencies=[Depends(verify_api_token)])


@router.get("/{run_id}/metrics")
async def get_metrics(run_id: str) -> dict:
    """Return all metrics for a run. (stub)"""
    return {"run_id": run_id, "metrics": [], "status": "not_implemented"}


@router.post("/{run_id}/metrics/poll")
async def poll_metrics(run_id: str) -> dict:
    """Manually trigger metrics collection. (stub)"""
    return {"run_id": run_id, "status": "not_implemented"}


@router.get("/{run_id}/retrospective")
async def get_retrospective(run_id: str) -> dict:
    """Return retrospective report if generated. (stub)"""
    return {"run_id": run_id, "status": "not_implemented"}
