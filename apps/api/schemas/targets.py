from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

TargetEnvironment = Literal["local", "kubernetes"]
TargetType = Literal["container", "namespace", "workload"]


class MonitorTargetUpsert(BaseModel):
    target_type: TargetType
    target_key: str = Field(min_length=1, max_length=255)
    display_name: str = Field(min_length=1, max_length=255)
    enabled: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpsertMonitorTargetsRequest(BaseModel):
    environment: TargetEnvironment = "local"
    targets: list[MonitorTargetUpsert] = Field(default_factory=list)


class UpsertMonitorTargetsResponse(BaseModel):
    updated: int


class MonitorTarget(BaseModel):
    id: UUID
    environment: TargetEnvironment
    target_type: TargetType
    target_key: str
    display_name: str
    enabled: bool
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class DiscoveredTarget(BaseModel):
    environment: TargetEnvironment
    target_type: TargetType
    target_key: str
    display_name: str
    metadata: dict[str, Any] = Field(default_factory=dict)
