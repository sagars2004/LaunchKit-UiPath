"""Artifact management API routes."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends

from backend.agents.revision_agent import RevisionAgent
from backend.api.deps import get_store, verify_api_token
from backend.core.exceptions import AgentError, NotFoundError, ValidationError
from backend.models.artifact import ARTIFACT_TYPES, ArtifactType
from backend.models.schemas import (
    ApproveArtifactResponse,
    ArtifactListResponse,
    ArtifactResponse,
    ReviseArtifactRequest,
    ReviseArtifactResponse,
)
from backend.services.artifact_store import ArtifactStore

logger = logging.getLogger("launchkit.routes.artifacts")

router = APIRouter(prefix="/runs", tags=["artifacts"], dependencies=[Depends(verify_api_token)])


def _validate_artifact_type(artifact_type: str) -> ArtifactType:
    if artifact_type not in ARTIFACT_TYPES:
        raise ValidationError(
            f"Invalid artifact type: {artifact_type}",
            f"Must be one of: {', '.join(ARTIFACT_TYPES)}",
        )
    return ArtifactType(artifact_type)


@router.get("/{run_id}/artifacts", response_model=ArtifactListResponse)
async def list_artifacts(
    run_id: UUID,
    store: ArtifactStore = Depends(get_store),
) -> ArtifactListResponse:
    """Return all artifacts with content and quality scores."""
    await store.get_run(run_id)
    artifacts = await store.list_artifacts(run_id)
    return ArtifactListResponse(run_id=run_id, artifacts=artifacts)


@router.get("/{run_id}/artifacts/{artifact_type}", response_model=ArtifactResponse)
async def get_artifact(
    run_id: UUID,
    artifact_type: str,
    store: ArtifactStore = Depends(get_store),
) -> ArtifactResponse:
    """Return a single artifact."""
    atype = _validate_artifact_type(artifact_type)
    artifact = await store.get_artifact(run_id, atype)
    return ArtifactResponse(artifact=artifact)


@router.post("/{run_id}/artifacts/{artifact_type}/approve", response_model=ApproveArtifactResponse)
async def approve_artifact(
    run_id: UUID,
    artifact_type: str,
    store: ArtifactStore = Depends(get_store),
) -> ApproveArtifactResponse:
    """Mark artifact as approved for publishing."""
    atype = _validate_artifact_type(artifact_type)
    artifact = await store.approve_artifact(run_id, atype)
    logger.info("Approved %s for run %s", atype.value, run_id)
    return ApproveArtifactResponse(artifact_type=atype, status=artifact.status.value)


@router.post("/{run_id}/artifacts/{artifact_type}/revise", response_model=ReviseArtifactResponse)
async def revise_artifact(
    run_id: UUID,
    artifact_type: str,
    body: ReviseArtifactRequest,
    store: ArtifactStore = Depends(get_store),
) -> ReviseArtifactResponse:
    """Revise artifact with developer feedback via revision agent."""
    atype = _validate_artifact_type(artifact_type)
    run = await store.get_run(run_id)

    try:
        artifact = await store.get_artifact(run_id, atype)
    except NotFoundError:
        raise ValidationError(
            f"Artifact {artifact_type} not generated yet",
            "Run POST /runs/{id}/generate first",
        ) from None

    if artifact.revision_count >= 3:
        raise ValidationError(
            "Max revisions reached",
            "This artifact has been revised 3 times — edit manually",
        )

    quality_scores = {}
    if run.quality_report and artifact_type in run.quality_report.get("artifacts", {}):
        quality_scores = run.quality_report["artifacts"][artifact_type]

    agent = RevisionAgent()
    try:
        new_content = await agent.run(
            artifact_type=artifact_type,
            original_content=artifact.content or "",
            feedback=body.feedback,
            quality_scores=quality_scores,
            hackathon_brief=run.hackathon_brief or {},
        )
    except Exception as exc:
        raise AgentError("Revision failed", str(exc)) from exc

    await store.create_revision(
        run_id,
        atype,
        body.feedback,
        artifact.content,
        new_content,
    )

    updated = await store.get_artifact(run_id, atype)
    return ReviseArtifactResponse(
        artifact_type=atype,
        content=new_content,
        revision_count=updated.revision_count,
    )
