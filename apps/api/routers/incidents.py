from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from apps.api.schemas.incident import (
    IncidentDetail,
    IncidentListItem,
    PaginatedResponse,
    WorkItemSummary,
)
from packages.data_access.models.analysis_orm import AnalysisOrm
from packages.data_access.models.incident_orm import IncidentOrm
from packages.data_access.session import get_db_session

router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])


@router.get("", response_model=PaginatedResponse[IncidentListItem])
async def list_incidents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> PaginatedResponse[IncidentListItem]:
    filters = []
    if status:
        filters.append(IncidentOrm.status == status)
    if priority:
        filters.append(IncidentOrm.priority == priority)
    if date_from:
        filters.append(IncidentOrm.created_at >= date_from)
    if date_to:
        filters.append(IncidentOrm.created_at <= date_to)

    count_stmt = select(func.count()).select_from(IncidentOrm)
    if filters:
        count_stmt = count_stmt.where(*filters)
    count_result = await db.execute(count_stmt)
    total: int = count_result.scalar_one()

    stmt = (
        select(IncidentOrm)
        .options(selectinload(IncidentOrm.work_items))
        .order_by(IncidentOrm.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    if filters:
        stmt = stmt.where(*filters)
    rows = await db.execute(stmt)
    incidents = list(rows.scalars().all())

    analyzed_ids: set[UUID] = set()
    if incidents:
        inc_ids = [i.id for i in incidents]
        analysis_stmt = select(AnalysisOrm.incident_id).where(
            AnalysisOrm.incident_id.in_(inc_ids)
        )
        analysis_rows = await db.execute(analysis_stmt)
        analyzed_ids = set(analysis_rows.scalars().all())

    items = [
        IncidentListItem(
            id=inc.id,
            exception_type=inc.exception_type,
            exception_message=inc.exception_message,
            priority=inc.priority,
            status=inc.status,
            created_at=inc.created_at,
            updated_at=inc.updated_at,
            has_analysis=inc.id in analyzed_ids,
            ado_bug_url=inc.work_items[0].ado_item_url if inc.work_items else None,
        )
        for inc in incidents
    ]

    return PaginatedResponse.build(items=items, total=total, page=page, page_size=page_size)


@router.get("/{incident_id}", response_model=IncidentDetail)
async def get_incident(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> IncidentDetail:
    stmt = (
        select(IncidentOrm)
        .where(IncidentOrm.id == incident_id)
        .options(
            selectinload(IncidentOrm.analyses),
            selectinload(IncidentOrm.work_items),
        )
    )
    result = await db.execute(stmt)
    incident = result.scalar_one_or_none()
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    analysis = incident.analyses[0] if incident.analyses else None
    pr_url = next((wi.pr_url for wi in incident.work_items if wi.pr_url), None)

    return IncidentDetail(
        id=incident.id,
        exception_type=incident.exception_type,
        exception_message=incident.exception_message,
        stack_trace=incident.stack_trace,
        priority=incident.priority,
        status=incident.status,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
        root_cause=analysis.root_cause if analysis else None,
        root_cause_json=analysis.root_cause_json if analysis else None,
        recommendations=list(analysis.recommendations) if analysis else [],
        code_snippets=list(analysis.code_snippets) if analysis else [],
        rag_results=list(analysis.rag_results) if analysis else [],
        agent_trace=list(analysis.agent_trace) if analysis else [],
        work_items=[
            WorkItemSummary(
                ado_item_id=wi.ado_item_id,
                ado_item_url=wi.ado_item_url,
                item_type=wi.item_type,
                pr_url=wi.pr_url,
            )
            for wi in incident.work_items
        ],
        approval_status=incident.approval_status,
        approved_by=incident.approved_by,
        approved_at=incident.approved_at,
        approved_recommendation_rank=incident.approved_recommendation_rank,
        pr_url=pr_url,
    )
