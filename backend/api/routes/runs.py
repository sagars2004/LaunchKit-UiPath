"""Run lifecycle API routes."""

import io
import json
import logging
import zipfile
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response, status
from fastapi.responses import StreamingResponse

from backend.agents.code_analyzer_agent import CodeAnalyzerAgent
from backend.agents.hackathon_intel_agent import HackathonIntelAgent
from backend.agents.quality_scorer_agent import QualityScorerAgent
from backend.agents.winner_researcher_agent import WinnerResearcherAgent
from backend.api.deps import get_store, verify_api_token
from backend.core.exceptions import AgentError, ValidationError, format_agent_error
from backend.models.artifact import ArtifactStatus, ArtifactType
from backend.models.content import DevpostCopy
from backend.models.run import RunStatus
from backend.models.schemas import (
    ActionResponse,
    CreateRunRequest,
    CreateRunResponse,
    PublishResponse,
    RunResponse,
)
from backend.services.artifact_store import ArtifactStore, get_artifact_store
from backend.services.content_generator import (
    ContentGenerator,
    generate_winning_brief,
)
from backend.services.devpost_service import get_devpost_service
from backend.services.github_service import get_github_service
from backend.services.linkedin_service import get_linkedin_service

logger = logging.getLogger("launchkit.routes.runs")

router = APIRouter(prefix="/runs", tags=["runs"], dependencies=[Depends(verify_api_token)])


@router.post("", response_model=CreateRunResponse)
async def create_run(
    body: CreateRunRequest,
    store: ArtifactStore = Depends(get_store),
) -> CreateRunResponse:
    """Create a new pipeline run and persist intake data."""
    intake = body.to_intake()
    run = await store.create_run(intake)
    logger.info("Created run %s for %s", run.id, intake.github_url)
    return CreateRunResponse(run_id=run.id, status=run.status)


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: UUID,
    store: ArtifactStore = Depends(get_store),
) -> RunResponse:
    """Return full run state including artifacts."""
    run = await store.get_run(run_id)
    artifacts = await store.list_artifacts(run_id)
    return RunResponse(run=run, artifacts=artifacts)


@router.post("/{run_id}/intel", response_model=ActionResponse)
async def trigger_intel(
    run_id: UUID,
    response: Response,
    background_tasks: BackgroundTasks,
    async_mode: bool = Query(False, alias="async"),
    store: ArtifactStore = Depends(get_store),
) -> ActionResponse:
    """Trigger Act I: hackathon intel + winner research + winning brief.

    Pass ``?async=true`` for Maestro/UiPath — returns in <2s; intel continues on
    the server. Use a Maestro timer or ``GET /runs/{id}`` before analyze.
    """
    run = await store.get_run(run_id)

    if run.hackathon_brief:
        return ActionResponse(
            run_id=run_id,
            status=RunStatus.INTAKE,
            message="Intelligence gathering already complete",
        )

    if async_mode:
        if run.status == RunStatus.INTELLIGENCE:
            response.status_code = status.HTTP_202_ACCEPTED
            return ActionResponse(
                run_id=run_id,
                status=RunStatus.INTELLIGENCE,
                message="Intel already in progress",
            )

        await store.update_run_status(run_id, RunStatus.INTELLIGENCE)
        background_tasks.add_task(_run_intel_job, run_id, store)
        response.status_code = status.HTTP_202_ACCEPTED
        return ActionResponse(
            run_id=run_id,
            status=RunStatus.INTELLIGENCE,
            message="Intel started — poll GET /runs/{id} until status is intake or failed",
        )

    return await _execute_intel(run_id, run, store)


async def _execute_intel(run_id: UUID, run, store: ArtifactStore) -> ActionResponse:
    await store.update_run_status(run_id, RunStatus.INTELLIGENCE)

    hackathon_url = run.intake.hackathon_url
    hackathon_name = run.intake.hackathon_name or "hackathon"
    track = run.intake.track_category

    try:
        intel_agent = HackathonIntelAgent()
        winner_agent = WinnerResearcherAgent()

        hackathon_brief, winner_patterns = await _gather_intel(
            intel_agent, winner_agent, hackathon_url, hackathon_name, track
        )

        winning_brief = await generate_winning_brief(
            hackathon_brief.model_dump(),
            winner_patterns.model_dump(),
        )

        update_fields: dict = {
            "hackathon_brief": hackathon_brief.model_dump(),
            "winner_patterns": winner_patterns.model_dump(),
            "winning_brief": winning_brief,
            "status": RunStatus.INTAKE.value,
        }
        if not run.intake.hackathon_name:
            intake_data = run.intake.model_dump()
            intake_data["hackathon_name"] = hackathon_brief.event_name
            update_fields["intake"] = intake_data

        await store.update_run(run_id, update_fields)

        return ActionResponse(
            run_id=run_id,
            status=RunStatus.INTAKE,
            message="Intelligence gathering complete",
        )
    except Exception as exc:
        await store.update_run(
            run_id,
            {"status": RunStatus.FAILED.value, "error_message": str(exc)},
        )
        raise AgentError("Intelligence gathering failed", format_agent_error(exc)) from exc


async def _run_intel_job(run_id: UUID, store: ArtifactStore | None = None) -> None:
    store = store or get_artifact_store()
    try:
        run = await store.get_run(run_id)
        await _execute_intel(run_id, run, store)
        logger.info("Background intel complete for run %s", run_id)
    except Exception as exc:
        logger.exception("Background intel failed for run %s: %s", run_id, exc)


async def _gather_intel(intel_agent, winner_agent, url, name, track):
    import asyncio

    return await asyncio.gather(
        intel_agent.run(url),
        winner_agent.run(name, track),
    )


@router.post("/{run_id}/analyze", response_model=ActionResponse)
async def trigger_analyze(
    run_id: UUID,
    store: ArtifactStore = Depends(get_store),
) -> ActionResponse:
    """Trigger code analysis agent."""
    run = await store.get_run(run_id)
    if not run.hackathon_brief:
        raise ValidationError(
            "Hackathon brief required",
            "Run POST /runs/{id}/intel before analyze",
        )

    await store.update_run_status(run_id, RunStatus.ANALYZING)

    try:
        agent = CodeAnalyzerAgent()
        intel, repo_context = await agent.run_with_context(
            run.intake.github_url,
            run.hackathon_brief,
        )

        await store.update_run(
            run_id,
            {
                "code_intelligence": intel.model_dump(),
                "repo_context": repo_context,
                "status": RunStatus.ANALYZING.value,
            },
        )
        return ActionResponse(
            run_id=run_id,
            status=RunStatus.ANALYZING,
            message="Code analysis complete",
        )
    except Exception as exc:
        await store.update_run(
            run_id,
            {"status": RunStatus.FAILED.value, "error_message": str(exc)},
        )
        raise AgentError("Code analysis failed", str(exc)) from exc


@router.post("/{run_id}/generate", response_model=ActionResponse)
async def trigger_generate(
    run_id: UUID,
    store: ArtifactStore = Depends(get_store),
) -> ActionResponse:
    """Generate all 5 content artifacts, score them, and store results."""
    run = await store.get_run(run_id)
    if not run.code_intelligence:
        raise ValidationError(
            "Code intelligence required",
            "Run POST /runs/{id}/analyze before generate",
        )
    if not run.hackathon_brief:
        raise ValidationError("Hackathon brief required", "Run intel first")

    winning_brief = run.winning_brief or {}
    await store.update_run_status(run_id, RunStatus.GENERATING)

    try:
        generator = ContentGenerator()
        artifacts = await generator.generate_all(
            run.code_intelligence,
            run.hackathon_brief,
            winning_brief,
        )

        for artifact_type, content in artifacts.items():
            await store.upsert_artifact(
                run_id,
                artifact_type,
                content,
                ArtifactStatus.GENERATED,
            )

        await store.update_run_status(run_id, RunStatus.SCORING)

        scorer = QualityScorerAgent()
        quality_report = await scorer.run(artifacts, run.hackathon_brief)

        for artifact_type, score in quality_report.artifacts.items():
            await store.upsert_artifact(
                run_id,
                artifact_type,
                artifacts.get(artifact_type, ""),
                ArtifactStatus.SCORED,
                quality_score=score.overall_score,
                quality_feedback=score.top_improvement,
            )

        await store.update_run(
            run_id,
            {
                "quality_report": quality_report.model_dump(),
                "status": RunStatus.REVIEWING.value,
            },
        )

        return ActionResponse(
            run_id=run_id,
            status=RunStatus.REVIEWING,
            message="Content generated and scored — ready for review",
        )
    except Exception as exc:
        await store.update_run(
            run_id,
            {"status": RunStatus.FAILED.value, "error_message": str(exc)},
        )
        raise AgentError("Content generation failed", str(exc)) from exc


@router.post("/{run_id}/publish", response_model=PublishResponse)
async def trigger_publish(
    run_id: UUID,
    store: ArtifactStore = Depends(get_store),
) -> PublishResponse:
    """Publish approved artifacts to GitHub, Devpost (RPA data), and LinkedIn."""
    run = await store.get_run(run_id)
    artifacts = await store.list_artifacts(run_id)
    approved = [a for a in artifacts if a.status == ArtifactStatus.APPROVED]

    if not approved:
        raise ValidationError(
            "No approved artifacts",
            "Approve at least one artifact before publishing",
        )

    await store.update_run_status(run_id, RunStatus.PUBLISHING)
    publishing_results: dict = {
        "github": {"status": "skipped"},
        "devpost": {"status": "skipped"},
        "linkedin": {"status": "skipped"},
    }

    github_svc = get_github_service()
    devpost_svc = get_devpost_service()
    linkedin_svc = get_linkedin_service()

    for artifact in approved:
        try:
            if artifact.artifact_type == ArtifactType.README:
                url = await github_svc.push_readme(
                    run.intake.github_url,
                    artifact.content or "",
                    "docs: update README via LaunchKit",
                )
                publishing_results["github"] = {"status": "success", "url": url}
                await store.upsert_artifact(
                    run_id,
                    ArtifactType.README,
                    artifact.content or "",
                    ArtifactStatus.PUBLISHED,
                )

            elif artifact.artifact_type == ArtifactType.DEVPOST_COPY:
                copy = DevpostCopy.model_validate_json(artifact.content or "{}")
                rpa_data = devpost_svc.format_for_rpa(copy)
                publishing_results["devpost"] = {
                    "status": "ready_for_rpa",
                    "fields": rpa_data,
                    "automation_log": "Formatted for UiPath RPA — run DevpostAutomation workflow",
                }

            elif artifact.artifact_type == ArtifactType.SOCIAL_CONTENT:
                social = json.loads(artifact.content or "{}")
                post_text = social.get("linkedin_post", "")
                hashtags = social.get("hashtags", [])
                full_post = post_text + "\n\n" + " ".join(f"#{t}" for t in hashtags)
                from backend.config import get_settings

                settings = get_settings()
                result = await linkedin_svc.post_update(full_post, settings.linkedin_access_token)
                if isinstance(result, dict):
                    publishing_results["linkedin"] = result
                else:
                    publishing_results["linkedin"] = {"status": "success", "post_id": result}

        except Exception as exc:
            logger.error("Publish failed for %s: %s", artifact.artifact_type, exc)
            platform = {
                ArtifactType.README: "github",
                ArtifactType.DEVPOST_COPY: "devpost",
                ArtifactType.SOCIAL_CONTENT: "linkedin",
            }.get(artifact.artifact_type, "unknown")
            publishing_results[platform] = {"status": "failed", "error": str(exc)}

    await store.update_run(
        run_id,
        {
            "publishing_results": publishing_results,
            "status": RunStatus.MONITORING.value,
        },
    )

    return PublishResponse(
        run_id=run_id,
        status=RunStatus.MONITORING,
        publishing_results=publishing_results,
    )


@router.get("/{run_id}/export")
async def export_run(
    run_id: UUID,
    store: ArtifactStore = Depends(get_store),
) -> StreamingResponse:
    """Download all artifacts and metadata as a zip file."""
    run = await store.get_run(run_id)
    artifacts = await store.list_artifacts(run_id)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("run.json", json.dumps(run.model_dump(), indent=2, default=str))
        if run.code_intelligence:
            zf.writestr(
                "code_intelligence.json",
                json.dumps(run.code_intelligence, indent=2),
            )
        if run.quality_report:
            zf.writestr(
                "quality_report.json",
                json.dumps(run.quality_report, indent=2),
            )
        for artifact in artifacts:
            ext = "md" if artifact.artifact_type.value in ("readme", "blog_draft") else "json"
            filename = f"artifacts/{artifact.artifact_type.value}.{ext}"
            zf.writestr(filename, artifact.content or "")

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=launchkit-{run_id}.zip"},
    )
