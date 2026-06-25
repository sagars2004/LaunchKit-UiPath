"""API request/response schemas."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from backend.models.artifact import Artifact, ArtifactType
from backend.models.metric import Metric, Retrospective
from backend.models.run import IntakeData, Run, RunStatus


class CreateRunRequest(BaseModel):
    github_url: HttpUrl | str
    hackathon_url: HttpUrl | str
    hackathon_name: str = ""
    track_category: str = ""
    team_members: list[str] = Field(default_factory=list)
    target_platforms: list[str] = Field(
        default_factory=lambda: ["devpost", "github", "linkedin", "blog"]
    )
    special_instructions: str = ""

    def to_intake(self) -> IntakeData:
        return IntakeData(
            github_url=str(self.github_url),
            hackathon_url=str(self.hackathon_url),
            hackathon_name=self.hackathon_name,
            track_category=self.track_category,
            team_members=self.team_members,
            target_platforms=self.target_platforms,
            special_instructions=self.special_instructions,
        )


class CreateRunResponse(BaseModel):
    run_id: UUID
    status: RunStatus


class RunResponse(BaseModel):
    run: Run
    artifacts: list[Artifact] = Field(default_factory=list)


class ArtifactListResponse(BaseModel):
    run_id: UUID
    artifacts: list[Artifact]


class ArtifactResponse(BaseModel):
    artifact: Artifact


class ReviseArtifactRequest(BaseModel):
    feedback: str = Field(min_length=1)


class ReviseArtifactResponse(BaseModel):
    artifact_type: ArtifactType
    content: str
    revision_count: int


class ApproveArtifactResponse(BaseModel):
    artifact_type: ArtifactType
    status: str


class MetricsResponse(BaseModel):
    run_id: UUID
    metrics: list[Metric]


class RetrospectiveResponse(BaseModel):
    run_id: UUID
    retrospective: Retrospective | None = None
    message: str = ""


class PublishResponse(BaseModel):
    run_id: UUID
    status: RunStatus
    publishing_results: dict[str, Any]


class ActionResponse(BaseModel):
    run_id: UUID
    status: RunStatus
    message: str = ""


class PipelineStatusResponse(BaseModel):
    """Lightweight poll target for Maestro / UiPath (fast GET, no large payloads)."""

    run_id: UUID
    status: RunStatus
    intel_ready: bool
    analyze_ready: bool
    generate_ready: bool
    failed: bool
    error_message: str | None = None
