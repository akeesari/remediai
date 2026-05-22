from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class WorkItemType(str, Enum):
    BUG = "bug"
    TASK = "task"


class WorkItem(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    ado_item_id: int
    ado_item_url: str
    item_type: WorkItemType = WorkItemType.BUG
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
