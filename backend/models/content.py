"""Content generation and quality scoring models."""

from pydantic import BaseModel, Field


class DevpostCopy(BaseModel):
    project_name: str
    tagline: str
    what_it_does: str
    how_i_built_it: str
    challenges: str
    accomplishments: str
    what_i_learned: str
    whats_next: str
    built_with: list[str] = Field(default_factory=list)


class DemoSegment(BaseModel):
    timestamp_start: str
    timestamp_end: str
    title: str
    narration: str
    screen_action: str
    key_point: str


class DemoScript(BaseModel):
    segments: list[DemoSegment] = Field(default_factory=list)
    total_duration_seconds: int = 300


class SocialContent(BaseModel):
    linkedin_post: str = ""
    hashtags: list[str] = Field(default_factory=list)


class ArtifactScore(BaseModel):
    overall_score: float = Field(ge=0.0, le=10.0)
    scores: dict[str, float] = Field(default_factory=dict)
    top_improvement: str = ""
    flag_for_auto_revision: bool = False


class QualityReport(BaseModel):
    artifacts: dict[str, ArtifactScore] = Field(default_factory=dict)
