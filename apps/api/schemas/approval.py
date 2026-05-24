from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ApproveRequest(BaseModel):
    recommendation_rank: int = Field(ge=1)
    approved_by: str = Field(min_length=1, max_length=255)


class RejectRequest(BaseModel):
    rejected_by: str = Field(min_length=1, max_length=255)
    reason: str = ""


class ApprovalResponse(BaseModel):
    incident_id: UUID
    approval_status: str
    approved_recommendation_rank: int | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
