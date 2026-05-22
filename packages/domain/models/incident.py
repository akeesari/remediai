import hashlib
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class IncidentPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IncidentStatus(str, Enum):
    NEW = "new"
    TRIAGING = "triaging"
    ANALYZED = "analyzed"
    BUG_CREATED = "bug_created"
    RESOLVED = "resolved"
    ANALYSIS_FAILED = "analysis_failed"


class Incident(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    correlation_id: UUID = Field(default_factory=uuid4)
    source: str
    exception_type: str
    exception_message: str
    stack_trace: str | None = None
    fingerprint: str = ""
    priority: IncidentPriority = IncidentPriority.MEDIUM
    status: IncidentStatus = IncidentStatus.NEW
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="before")
    @classmethod
    def derive_fingerprint(cls, values: dict[str, Any]) -> dict[str, Any]:
        if not values.get("fingerprint"):
            exc_type = str(values.get("exception_type", ""))
            exc_msg = str(values.get("exception_message", ""))[:200]
            raw = f"{exc_type}:{exc_msg}"
            values["fingerprint"] = hashlib.sha256(raw.encode()).hexdigest()
        return values
