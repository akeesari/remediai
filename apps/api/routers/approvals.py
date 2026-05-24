from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.schemas.approval import ApprovalResponse, ApproveRequest, RejectRequest
from packages.data_access.models.analysis_orm import AnalysisOrm
from packages.data_access.models.audit_log_orm import AuditLogOrm
from packages.data_access.models.incident_orm import IncidentOrm
from packages.data_access.session import get_db_session
from packages.domain.models.audit import AgentTraceEntry

router = APIRouter(prefix="/api/v1/incidents", tags=["approvals"])


async def _get_incident_or_404(
    incident_id: UUID,
    db: AsyncSession,
) -> IncidentOrm:
    stmt = select(IncidentOrm).where(IncidentOrm.id == incident_id)
    result = await db.execute(stmt)
    incident = result.scalar_one_or_none()
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


async def _get_latest_analysis(incident_id: UUID, db: AsyncSession) -> AnalysisOrm | None:
    stmt = (
        select(AnalysisOrm)
        .where(AnalysisOrm.incident_id == incident_id)
        .order_by(AnalysisOrm.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def _write_audit(
    db: AsyncSession,
    incident_id: UUID,
    action: str,
    actor: str,
    metadata: dict[str, object],
) -> None:
    entry = AuditLogOrm(
        id=uuid.uuid4(),
        incident_id=incident_id,
        agent_name="human_approval",
        action=action,
        actor_identity=actor,
        log_metadata=metadata,
        timestamp=datetime.now(tz=UTC),
    )
    db.add(entry)


def _append_human_approval_trace(
    analysis: AnalysisOrm | None,
    *,
    input_summary: str,
    output_summary: str,
) -> None:
    if analysis is None:
        return
    trace_entries: list[dict[str, Any]] = list(analysis.agent_trace or [])
    trace_entry = AgentTraceEntry(
        agent_name="human_approval",
        prompt_version=None,
        input_summary=input_summary,
        output_summary=output_summary,
        latency_ms=0,
        error=None,
    )
    trace_entries.append(trace_entry.model_dump())
    analysis.agent_trace = trace_entries


@router.post("/{incident_id}/approve", response_model=ApprovalResponse)
async def approve_incident(
    incident_id: UUID,
    body: ApproveRequest,
    db: AsyncSession = Depends(get_db_session),
) -> ApprovalResponse:
    incident = await _get_incident_or_404(incident_id, db)

    if incident.status != "analyzed":
        raise HTTPException(
            status_code=409,
            detail=f"Incident status is '{incident.status}'; only 'analyzed' incidents can be approved.",
        )

    analysis = await _get_latest_analysis(incident_id, db)
    recommendations: list[dict[str, Any]] = (
        list(analysis.recommendations) if analysis and analysis.recommendations else []
    )
    if body.recommendation_rank < 1 or body.recommendation_rank > len(recommendations):
        raise HTTPException(
            status_code=422,
            detail=f"recommendation_rank {body.recommendation_rank} is out of range (1–{len(recommendations)}).",
        )

    now = datetime.now(tz=UTC)
    incident.approval_status = "approved"
    incident.approved_by = body.approved_by
    incident.approved_at = now
    incident.approved_recommendation_rank = body.recommendation_rank
    _append_human_approval_trace(
        analysis,
        input_summary=f"recommendation_rank={body.recommendation_rank}",
        output_summary=f"status=approved, by={body.approved_by}",
    )

    _write_audit(
        db,
        incident_id=incident_id,
        action="approved",
        actor=body.approved_by,
        metadata={
            "recommendation_rank": body.recommendation_rank,
            "output_summary": f"status=approved, by={body.approved_by}",
        },
    )

    await db.commit()
    await db.refresh(incident)

    return ApprovalResponse(
        incident_id=incident.id,
        approval_status="approved",
        approved_recommendation_rank=incident.approved_recommendation_rank,
        approved_by=incident.approved_by,
        approved_at=incident.approved_at,
    )


@router.post("/{incident_id}/reject", response_model=ApprovalResponse)
async def reject_incident(
    incident_id: UUID,
    body: RejectRequest,
    db: AsyncSession = Depends(get_db_session),
) -> ApprovalResponse:
    incident = await _get_incident_or_404(incident_id, db)
    analysis = await _get_latest_analysis(incident_id, db)

    now = datetime.now(tz=UTC)
    incident.approval_status = "rejected"
    incident.approved_by = body.rejected_by
    incident.approved_at = now
    incident.approved_recommendation_rank = None
    _append_human_approval_trace(
        analysis,
        input_summary="recommendation_rank=none",
        output_summary=f"status=rejected, by={body.rejected_by}",
    )

    _write_audit(
        db,
        incident_id=incident_id,
        action="rejected",
        actor=body.rejected_by,
        metadata={
            "reason": body.reason,
            "output_summary": f"status=rejected, by={body.rejected_by}",
        },
    )

    await db.commit()
    await db.refresh(incident)

    return ApprovalResponse(
        incident_id=incident.id,
        approval_status="rejected",
        approved_by=incident.approved_by,
        approved_at=incident.approved_at,
    )
