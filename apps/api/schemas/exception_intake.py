from __future__ import annotations

from pydantic import BaseModel, Field


class ExceptionIngestPayload(BaseModel):
    exception_type: str = Field(..., min_length=1, max_length=255)
    exception_message: str = Field(..., min_length=1, max_length=2000)
    stack_trace: str = Field(default="", max_length=50_000)
    source: str = Field(default="webhook", max_length=255)
    application_name: str = Field(default="unknown", max_length=255)
    environment: str = Field(default="unknown", max_length=100)
    language: str = Field(default="unknown", max_length=50)


# Upload uses the same schema — separate endpoint for UI / manual use
ExceptionUploadPayload = ExceptionIngestPayload


class ExceptionIntakeResponse(BaseModel):
    status: str  # "created" | "duplicate"
    incident_id: str | None = None
