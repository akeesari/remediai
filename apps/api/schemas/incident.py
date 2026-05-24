from __future__ import annotations

from datetime import datetime
from math import ceil
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def build(
        cls,
        items: list[T],
        total: int,
        page: int,
        page_size: int,
    ) -> PaginatedResponse[T]:
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=ceil(total / page_size) if total > 0 else 0,
        )


class WorkItemSummary(BaseModel):
    ado_item_id: int
    ado_item_url: str
    item_type: str
    pr_url: str | None = None


class IncidentListItem(BaseModel):
    id: UUID
    exception_type: str
    exception_message: str
    priority: str
    status: str
    created_at: datetime
    updated_at: datetime
    has_analysis: bool
    ado_bug_url: str | None = None


class IncidentDetail(BaseModel):
    id: UUID
    exception_type: str
    exception_message: str
    stack_trace: str | None = None
    priority: str
    status: str
    created_at: datetime
    updated_at: datetime
    root_cause: str | None = None
    root_cause_json: dict[str, Any] | None = None
    recommendations: list[dict[str, Any]] = []
    code_snippets: list[dict[str, Any]] = []
    rag_results: list[dict[str, Any]] = []
    agent_trace: list[dict[str, Any]] = []
    work_items: list[WorkItemSummary] = []
    # Phase 19 — approval gate
    approval_status: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    approved_recommendation_rank: int | None = None
    pr_url: str | None = None
