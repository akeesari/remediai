from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.data_access.models.incident_orm import IncidentOrm
from packages.domain.models.incident import Incident
from packages.integrations.azure_monitor.client import AzureMonitorClient

logger = structlog.get_logger()


class IngestionConnector:
    """Fetches new exceptions from Azure Monitor and persists them as incidents."""

    def __init__(self, session: AsyncSession, monitor_client: AzureMonitorClient) -> None:
        self._session = session
        self._monitor_client = monitor_client

    async def run(self, lookback_minutes: int = 10) -> list[Incident]:
        """Fetch, deduplicate, and persist new incidents. Returns only newly created ones."""
        raw = await self._monitor_client.fetch_recent_exceptions(lookback_minutes=lookback_minutes)
        if not raw:
            logger.info("ingestion_no_exceptions_found")
            return []

        new_incidents: list[Incident] = []
        for incident in raw:
            existing = await self._session.scalar(
                select(IncidentOrm).where(IncidentOrm.fingerprint == incident.fingerprint)
            )
            if existing is not None:
                logger.debug("ingestion_duplicate_skipped", fingerprint=incident.fingerprint)
                continue

            self._session.add(_to_orm(incident))
            new_incidents.append(incident)
            logger.info(
                "ingestion_incident_created",
                fingerprint=incident.fingerprint,
                source=incident.source,
                exception_type=incident.exception_type,
            )

        if new_incidents:
            await self._session.flush()

        logger.info(
            "ingestion_run_complete",
            total_fetched=len(raw),
            new_incidents=len(new_incidents),
            duplicates_skipped=len(raw) - len(new_incidents),
        )
        return new_incidents


def _to_orm(incident: Incident) -> IncidentOrm:
    now = datetime.now(UTC)
    return IncidentOrm(
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
        created_at=incident.created_at or now,
        updated_at=incident.updated_at or now,
    )
