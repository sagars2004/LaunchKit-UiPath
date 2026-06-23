"""Supabase artifact store — async wrapper around the Supabase Python SDK."""

import asyncio
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from supabase import Client, create_client

from backend.config import Settings, get_settings
from backend.core.exceptions import NotFoundError, SupabaseError
from backend.models.artifact import Artifact, ArtifactStatus, ArtifactType, Revision
from backend.models.metric import Metric, Retrospective
from backend.models.run import AnalyticsSnapshot, IntakeData, PublishingResults, Run, RunStatus

logger = logging.getLogger("launchkit.store")

_client: Client | None = None


def _get_client(settings: Settings | None = None) -> Client:
    global _client
    settings = settings or get_settings()
    if not settings.supabase_url or not settings.supabase_service_key:
        raise SupabaseError(
            "Supabase not configured",
            "Set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env",
        )
    if _client is None:
        _client = create_client(settings.supabase_url, settings.supabase_service_key)
    return _client


def _parse_run(row: dict[str, Any]) -> Run:
    intake_raw = row.get("intake") or {}
    pub_raw = row.get("publishing_results") or {}
    analytics_raw = row.get("analytics") or {}

    return Run(
        id=UUID(row["id"]),
        status=RunStatus(row["status"]),
        intake=IntakeData(**intake_raw),
        hackathon_brief=row.get("hackathon_brief"),
        winner_patterns=row.get("winner_patterns"),
        winning_brief=row.get("winning_brief"),
        repo_context=row.get("repo_context"),
        code_intelligence=row.get("code_intelligence"),
        quality_report=row.get("quality_report"),
        publishing_results=PublishingResults(**pub_raw) if pub_raw else PublishingResults(),
        analytics=AnalyticsSnapshot(**analytics_raw) if analytics_raw else AnalyticsSnapshot(),
        error_message=row.get("error_message"),
        created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
        updated_at=datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00")),
    )


def _parse_artifact(row: dict[str, Any]) -> Artifact:
    return Artifact(
        id=UUID(row["id"]),
        run_id=UUID(row["run_id"]),
        artifact_type=ArtifactType(row["artifact_type"]),
        status=ArtifactStatus(row["status"]),
        content=row.get("content"),
        quality_score=row.get("quality_score"),
        quality_feedback=row.get("quality_feedback"),
        published_url=row.get("published_url"),
        revision_count=row.get("revision_count", 0),
        created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
        updated_at=datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00")),
    )


def _parse_metric(row: dict[str, Any]) -> Metric:
    return Metric(
        id=UUID(row["id"]),
        run_id=UUID(row["run_id"]),
        source=row["source"],
        metric_type=row["metric_type"],
        value=row["value"],
        delta=row.get("delta"),
        recorded_at=datetime.fromisoformat(row["recorded_at"].replace("Z", "+00:00")),
    )


def _parse_revision(row: dict[str, Any]) -> Revision:
    return Revision(
        id=UUID(row["id"]),
        run_id=UUID(row["run_id"]),
        artifact_type=ArtifactType(row["artifact_type"]),
        feedback=row["feedback"],
        previous_content=row.get("previous_content"),
        new_content=row["new_content"],
        created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
    )


async def _run_sync(fn, *args, **kwargs):
    return await asyncio.to_thread(fn, *args, **kwargs)


class ArtifactStore:
    """Async Supabase client wrapper for LaunchKit persistence."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = _get_client(self.settings)

    async def create_run(self, intake_data: IntakeData) -> Run:
        payload = {
            "status": RunStatus.INTAKE.value,
            "intake": intake_data.model_dump(),
        }

        def _insert():
            result = self._client.table("runs").insert(payload).execute()
            if not result.data:
                raise SupabaseError("Failed to create run", "Insert returned no data")
            return result.data[0]

        row = await _run_sync(_insert)
        run = _parse_run(row)
        logger.info("Created run %s", run.id)
        return run

    async def get_run(self, run_id: UUID) -> Run:
        def _fetch():
            result = (
                self._client.table("runs")
                .select("*")
                .eq("id", str(run_id))
                .maybe_single()
                .execute()
            )
            return result.data

        row = await _run_sync(_fetch)
        if not row:
            raise NotFoundError(f"Run {run_id} not found", f"No run with id {run_id}")
        return _parse_run(row)

    async def update_run_status(self, run_id: UUID, status: RunStatus) -> Run:
        return await self.update_run(run_id, {"status": status.value})

    async def update_run(self, run_id: UUID, fields: dict[str, Any]) -> Run:
        def _update():
            result = self._client.table("runs").update(fields).eq("id", str(run_id)).execute()
            if not result.data:
                raise NotFoundError(f"Run {run_id} not found", f"No run with id {run_id}")
            return result.data[0]

        row = await _run_sync(_update)
        return _parse_run(row)

    async def upsert_artifact(
        self,
        run_id: UUID,
        artifact_type: ArtifactType | str,
        content: str,
        status: ArtifactStatus | str = ArtifactStatus.GENERATED,
        quality_score: float | None = None,
        quality_feedback: str | None = None,
    ) -> Artifact:
        atype = artifact_type.value if isinstance(artifact_type, ArtifactType) else artifact_type
        astatus = status.value if isinstance(status, ArtifactStatus) else status

        payload: dict[str, Any] = {
            "run_id": str(run_id),
            "artifact_type": atype,
            "content": content,
            "status": astatus,
        }
        if quality_score is not None:
            payload["quality_score"] = quality_score
        if quality_feedback is not None:
            payload["quality_feedback"] = quality_feedback

        def _upsert():
            result = (
                self._client.table("artifacts")
                .upsert(payload, on_conflict="run_id,artifact_type")
                .execute()
            )
            if not result.data:
                raise SupabaseError("Failed to upsert artifact", "Upsert returned no data")
            return result.data[0]

        row = await _run_sync(_upsert)
        return _parse_artifact(row)

    async def get_artifact(self, run_id: UUID, artifact_type: ArtifactType | str) -> Artifact:
        atype = artifact_type.value if isinstance(artifact_type, ArtifactType) else artifact_type

        def _fetch():
            result = (
                self._client.table("artifacts")
                .select("*")
                .eq("run_id", str(run_id))
                .eq("artifact_type", atype)
                .maybe_single()
                .execute()
            )
            return result.data

        row = await _run_sync(_fetch)
        if not row:
            raise NotFoundError(
                f"Artifact {atype} not found",
                f"No {atype} artifact for run {run_id}",
            )
        return _parse_artifact(row)

    async def list_artifacts(self, run_id: UUID) -> list[Artifact]:
        def _fetch():
            result = self._client.table("artifacts").select("*").eq("run_id", str(run_id)).execute()
            return result.data or []

        rows = await _run_sync(_fetch)
        return [_parse_artifact(r) for r in rows]

    async def approve_artifact(self, run_id: UUID, artifact_type: ArtifactType | str) -> Artifact:
        atype = artifact_type.value if isinstance(artifact_type, ArtifactType) else artifact_type

        def _update():
            result = (
                self._client.table("artifacts")
                .update({"status": ArtifactStatus.APPROVED.value})
                .eq("run_id", str(run_id))
                .eq("artifact_type", atype)
                .execute()
            )
            if not result.data:
                raise NotFoundError(
                    f"Artifact {atype} not found",
                    f"No {atype} artifact for run {run_id}",
                )
            return result.data[0]

        row = await _run_sync(_update)
        return _parse_artifact(row)

    async def create_revision(
        self,
        run_id: UUID,
        artifact_type: ArtifactType | str,
        feedback: str,
        previous_content: str | None,
        new_content: str,
    ) -> Revision:
        atype = artifact_type.value if isinstance(artifact_type, ArtifactType) else artifact_type
        payload = {
            "run_id": str(run_id),
            "artifact_type": atype,
            "feedback": feedback,
            "previous_content": previous_content,
            "new_content": new_content,
        }

        def _insert():
            rev_result = self._client.table("revisions").insert(payload).execute()
            art = (
                self._client.table("artifacts")
                .select("revision_count")
                .eq("run_id", str(run_id))
                .eq("artifact_type", atype)
                .maybe_single()
                .execute()
            )
            current_count = (art.data or {}).get("revision_count", 0)
            self._client.table("artifacts").update(
                {
                    "content": new_content,
                    "status": ArtifactStatus.GENERATED.value,
                    "revision_count": current_count + 1,
                }
            ).eq("run_id", str(run_id)).eq("artifact_type", atype).execute()

            if not rev_result.data:
                raise SupabaseError("Failed to create revision", "Insert returned no data")
            return rev_result.data[0]

        row = await _run_sync(_insert)
        return _parse_revision(row)

    async def record_metric(
        self,
        run_id: UUID,
        source: str,
        metric_type: str,
        value: int,
        delta: int | None = None,
    ) -> Metric:
        payload = {
            "run_id": str(run_id),
            "source": source,
            "metric_type": metric_type,
            "value": value,
            "delta": delta,
        }

        def _insert():
            result = self._client.table("metrics").insert(payload).execute()
            if not result.data:
                raise SupabaseError("Failed to record metric", "Insert returned no data")
            return result.data[0]

        row = await _run_sync(_insert)
        return _parse_metric(row)

    async def get_metrics(self, run_id: UUID) -> list[Metric]:
        def _fetch():
            result = (
                self._client.table("metrics")
                .select("*")
                .eq("run_id", str(run_id))
                .order("recorded_at", desc=True)
                .execute()
            )
            return result.data or []

        rows = await _run_sync(_fetch)
        return [_parse_metric(r) for r in rows]

    async def save_retrospective(self, run_id: UUID, content: str) -> Retrospective:
        payload = {"run_id": str(run_id), "content": content}

        def _upsert():
            result = (
                self._client.table("retrospectives").upsert(payload, on_conflict="run_id").execute()
            )
            if not result.data:
                raise SupabaseError("Failed to save retrospective", "Upsert returned no data")
            row = result.data[0]
            return Retrospective(
                id=UUID(row["id"]),
                run_id=UUID(row["run_id"]),
                content=row["content"],
                created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00")),
            )

        return await _run_sync(_upsert)

    async def get_retrospective(self, run_id: UUID) -> Retrospective | None:
        def _fetch():
            result = (
                self._client.table("retrospectives")
                .select("*")
                .eq("run_id", str(run_id))
                .maybe_single()
                .execute()
            )
            return result.data

        row = await _run_sync(_fetch)
        if not row:
            return None
        return Retrospective(
            id=UUID(row["id"]),
            run_id=UUID(row["run_id"]),
            content=row["content"],
            created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00")),
        )


def get_artifact_store(settings: Settings | None = None) -> ArtifactStore:
    return ArtifactStore(settings)
