"""Artifact models."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel


class ArtifactType(str, Enum):
    README = "readme"
    DEVPOST_COPY = "devpost_copy"
    DEMO_SCRIPT = "demo_script"
    SOCIAL_CONTENT = "social_content"
    BLOG_DRAFT = "blog_draft"


class ArtifactStatus(str, Enum):
    PENDING = "pending"
    GENERATED = "generated"
    SCORED = "scored"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"


ARTIFACT_TYPES = [t.value for t in ArtifactType]


class Artifact(BaseModel):
    id: UUID
    run_id: UUID
    artifact_type: ArtifactType
    status: ArtifactStatus = ArtifactStatus.PENDING
    content: str | None = None
    quality_score: float | None = None
    quality_feedback: str | None = None
    published_url: str | None = None
    revision_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class Revision(BaseModel):
    id: UUID
    run_id: UUID
    artifact_type: ArtifactType
    feedback: str
    previous_content: str | None = None
    new_content: str
    created_at: datetime

    model_config = {"from_attributes": True}
