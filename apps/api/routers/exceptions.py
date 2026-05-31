"""Generic exception intake endpoints.

POST /api/v1/exceptions/ingest  — webhook intake for any application
POST /api/v1/exceptions/upload  — manual stack trace upload

Both endpoints fingerprint, deduplicate, and persist exceptions as incidents.
They are always registered (not local-mode only) so any application can feed
exceptions into RemediAI regardless of whether Azure Monitor is configured.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.auth import require_auth
from apps.api.schemas.exception_intake import (
    ExceptionIngestPayload,
    ExceptionIntakeResponse,
    ExceptionUploadPayload,
)
from packages.data_access.models.incident_orm import IncidentOrm
from packages.data_access.session import get_db_session
from packages.domain.models.incident import Incident

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/exceptions", tags=["exceptions"])


@router.post("/ingest", response_model=ExceptionIntakeResponse)
async def ingest_exception(
    payload: ExceptionIngestPayload,
    db: AsyncSession = Depends(get_db_session),
    _auth: None = Depends(require_auth),
) -> ExceptionIntakeResponse:
    """Webhook endpoint — applications POST exceptions directly."""
    return await _create_incident(payload, db)


@router.post("/upload", response_model=ExceptionIntakeResponse)
async def upload_exception(
    payload: ExceptionUploadPayload,
    db: AsyncSession = Depends(get_db_session),
    _auth: None = Depends(require_auth),
) -> ExceptionIntakeResponse:
    """Manual upload — developers paste a stack trace from any environment."""
    return await _create_incident(payload, db)


async def _create_incident(
    payload: ExceptionIngestPayload,
    db: AsyncSession,
) -> ExceptionIntakeResponse:
    incident = Incident(
        source=payload.source,
        exception_type=payload.exception_type,
        exception_message=payload.exception_message,
        stack_trace=payload.stack_trace or None,
        raw_payload={
            "application_name": payload.application_name,
            "environment": payload.environment,
            "language": payload.language,
            "source": payload.source,
            "ingested_via": "api",
            "ingested_at": datetime.now(UTC).isoformat(),
        },
    )

    existing = await db.scalar(
        select(IncidentOrm).where(IncidentOrm.fingerprint == incident.fingerprint)
    )
    if existing is not None:
        logger.debug(
            "exception_intake_duplicate",
            fingerprint=incident.fingerprint,
            exception_type=payload.exception_type,
        )
        return ExceptionIntakeResponse(status="duplicate", incident_id=None)

    now = datetime.now(UTC)
    orm = IncidentOrm(
        id=incident.id,
        correlation_id=incident.correlation_id,
        source=incident.source,
        exception_type=incident.exception_type,
        exception_message=incident.exception_message,
        stack_trace=incident.stack_trace,
        fingerprint=incident.fingerprint,
        priority=incident.priority.value,
        status=incident.status.value,
        raw_payload=incident.raw_payload,
        created_at=now,
        updated_at=now,
    )
    db.add(orm)
    await db.commit()

    logger.info(
        "exception_intake_created",
        incident_id=str(incident.id),
        exception_type=payload.exception_type,
        source=payload.source,
        environment=payload.environment,
    )
    return ExceptionIntakeResponse(status="created", incident_id=str(incident.id))
