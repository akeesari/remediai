from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.core.config import Settings, get_settings
from apps.worker.ingestion.connector import IngestionConnector
from packages.domain.models.events import IncidentEvent
from packages.domain.models.incident import Incident
from packages.integrations.azure_monitor.client import AzureMonitorClient
from packages.integrations.service_bus.publisher import ServiceBusPublisher

logger = structlog.get_logger()


class IngestionScheduler:
    """Polls Azure Monitor, persists new incidents, and publishes events to Service Bus."""

    def __init__(
        self,
        settings: Settings | None = None,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        if session_factory is None:
            from packages.data_access.session import async_session_factory

            session_factory = async_session_factory
        self._session_factory = session_factory

    async def run_once(self) -> list[IncidentEvent]:
        """Execute one ingestion cycle. Returns the events published to Service Bus."""
        s = self._settings
        log = logger.bind(workspace_id=s.azure_monitor_workspace_id)
        log.info("ingestion_cycle_start")

        events: list[IncidentEvent] = []

        async with self._session_factory() as session:
            try:
                if not s.azure_monitor_workspace_id:
                    logger.info("ingestion_skipped_no_monitor_config")
                    return []

                async with AzureMonitorClient(workspace_id=s.azure_monitor_workspace_id) as monitor:
                    connector = IngestionConnector(session=session, monitor_client=monitor)
                    new_incidents = await connector.run(
                        lookback_minutes=s.ingestion_lookback_minutes
                    )

                if new_incidents:
                    events = [_to_event(inc) for inc in new_incidents]
                    if s.azure_servicebus_connection_string or (
                        s.azure_servicebus_namespace and s.azure_servicebus_namespace != "localhost"
                    ):
                        async with ServiceBusPublisher(
                            namespace=s.azure_servicebus_namespace,
                            topic=s.azure_servicebus_topic,
                            connection_string=s.azure_servicebus_connection_string,
                        ) as publisher:
                            await publisher.publish_batch(events)
                    else:
                        logger.warning(
                            "servicebus_publish_skipped",
                            reason="missing_connection_string_or_external_namespace",
                        )

                await session.commit()
            except Exception:
                await session.rollback()
                raise

        log.info("ingestion_cycle_complete", new_incidents=len(events))
        return events

    async def run_forever(self) -> None:
        """Run ingestion cycles indefinitely, sleeping between runs."""
        interval = self._settings.ingestion_poll_interval_seconds
        logger.info("ingestion_scheduler_start", poll_interval_seconds=interval)

        while True:
            try:
                await self.run_once()
            except Exception as exc:
                logger.error("ingestion_cycle_failed", error=str(exc))

            await asyncio.sleep(interval)


def _to_event(incident: Incident) -> IncidentEvent:
    return IncidentEvent(
        incident_id=incident.id,
        correlation_id=incident.correlation_id,
        source=incident.source,
        exception_type=incident.exception_type,
        exception_message=incident.exception_message,
        fingerprint=incident.fingerprint,
        priority=incident.priority.value,
        status=incident.status.value,
        published_at=datetime.now(UTC),
    )
