"""Run lifecycle API routes — STEP 7 implementation pending."""

from fastapi import APIRouter, Depends

from backend.api.deps import verify_api_token

router = APIRouter(prefix="/runs", tags=["runs"], dependencies=[Depends(verify_api_token)])


@router.post("")
async def create_run() -> dict:
    """Create a new pipeline run. (stub)"""
    return {"status": "not_implemented", "message": "STEP 7 pending"}


@router.get("/{run_id}")
async def get_run(run_id: str) -> dict:
    """Get full run state. (stub)"""
    return {"run_id": run_id, "status": "not_implemented"}


@router.post("/{run_id}/intel")
async def trigger_intel(run_id: str) -> dict:
    """Trigger Act I intelligence gathering. (stub)"""
    return {"run_id": run_id, "status": "not_implemented"}


@router.post("/{run_id}/analyze")
async def trigger_analyze(run_id: str) -> dict:
    """Trigger code analysis. (stub)"""
    return {"run_id": run_id, "status": "not_implemented"}


@router.post("/{run_id}/generate")
async def trigger_generate(run_id: str) -> dict:
    """Trigger content generation. (stub)"""
    return {"run_id": run_id, "status": "not_implemented"}


@router.post("/{run_id}/publish")
async def trigger_publish(run_id: str) -> dict:
    """Trigger publishing for approved artifacts. (stub)"""
    return {"run_id": run_id, "status": "not_implemented"}


@router.get("/{run_id}/export")
async def export_run(run_id: str) -> dict:
    """Download submission package as zip. (stub)"""
    return {"run_id": run_id, "status": "not_implemented"}
