from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AgentTraceEntry(BaseModel):
    agent_name: str
    prompt_version: str | None = None
    input_summary: str
    output_summary: str
    llm_model: str | None = None
    tokens_used: int | None = None
    latency_ms: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    error: str | None = None


class AuditLog(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    incident_id: UUID | None = None
    agent_name: str
    action: str
    input_summary: str | None = None
    output_summary: str | None = None
    actor_identity: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
