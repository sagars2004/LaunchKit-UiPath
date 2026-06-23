"""Run state machine models."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    INTAKE = "intake"
    INTELLIGENCE = "intelligence"
    ANALYZING = "analyzing"
    GENERATING = "generating"
    SCORING = "scoring"
    REVIEWING = "reviewing"
    PUBLISHING = "publishing"
    MONITORING = "monitoring"
    COMPLETE = "complete"
    FAILED = "failed"


class IntakeData(BaseModel):
    github_url: str
    hackathon_url: str
    hackathon_name: str = ""
    track_category: str = ""
    team_members: list[str] = Field(default_factory=list)
    target_platforms: list[str] = Field(
        default_factory=lambda: ["devpost", "github", "linkedin", "blog"]
    )
    special_instructions: str = ""


class PublishResult(BaseModel):
    status: str = "skipped"
    url: str | None = None
    committed_at: datetime | None = None
    automation_log: str | None = None
    post_id: str | None = None


class PublishingResults(BaseModel):
    github: PublishResult = Field(default_factory=PublishResult)
    devpost: PublishResult = Field(default_factory=PublishResult)
    linkedin: PublishResult = Field(default_factory=PublishResult)


class AnalyticsSnapshot(BaseModel):
    last_polled: datetime | None = None
    devpost_views: int = 0
    devpost_likes: int = 0
    github_stars: int = 0
    linkedin_reactions: int = 0
    is_finalist: bool = False
    is_winner: bool = False


class Run(BaseModel):
    id: UUID
    status: RunStatus = RunStatus.INTAKE
    intake: IntakeData
    hackathon_brief: dict[str, Any] | None = None
    winner_patterns: dict[str, Any] | None = None
    winning_brief: dict[str, Any] | None = None
    repo_context: dict[str, Any] | None = None
    code_intelligence: dict[str, Any] | None = None
    quality_report: dict[str, Any] | None = None
    publishing_results: PublishingResults = Field(default_factory=PublishingResults)
    analytics: AnalyticsSnapshot = Field(default_factory=AnalyticsSnapshot)
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
