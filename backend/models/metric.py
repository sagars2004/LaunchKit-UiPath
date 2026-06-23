"""Metrics and retrospective models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class Metric(BaseModel):
    id: UUID
    run_id: UUID
    source: str
    metric_type: str
    value: int
    delta: int | None = None
    recorded_at: datetime

    model_config = {"from_attributes": True}


class Retrospective(BaseModel):
    id: UUID
    run_id: UUID
    content: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
