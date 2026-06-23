"""Artifact management API routes — STEP 7 implementation pending."""

from fastapi import APIRouter, Depends

from backend.api.deps import verify_api_token

router = APIRouter(prefix="/runs", tags=["artifacts"], dependencies=[Depends(verify_api_token)])


@router.get("/{run_id}/artifacts")
async def list_artifacts(run_id: str) -> dict:
    """Return all artifacts with content and quality scores. (stub)"""
    return {"run_id": run_id, "artifacts": [], "status": "not_implemented"}


@router.get("/{run_id}/artifacts/{artifact_type}")
async def get_artifact(run_id: str, artifact_type: str) -> dict:
    """Return a single artifact. (stub)"""
    return {"run_id": run_id, "artifact_type": artifact_type, "status": "not_implemented"}


@router.post("/{run_id}/artifacts/{artifact_type}/approve")
async def approve_artifact(run_id: str, artifact_type: str) -> dict:
    """Mark artifact as approved. (stub)"""
    return {"run_id": run_id, "artifact_type": artifact_type, "status": "not_implemented"}


@router.post("/{run_id}/artifacts/{artifact_type}/revise")
async def revise_artifact(run_id: str, artifact_type: str) -> dict:
    """Revise artifact with developer feedback. (stub)"""
    return {"run_id": run_id, "artifact_type": artifact_type, "status": "not_implemented"}
