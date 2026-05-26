from __future__ import annotations

import asyncio

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.worker.ingestion.connector import IngestionConnector
from packages.config.settings import Settings, get_settings
from packages.domain.models.incident import Incident
from packages.integrations.azure_monitor.client import AzureMonitorClient

logger = structlog.get_logger()


class IngestionScheduler:
    """Polls Azure Monitor, persists new incidents to PostgreSQL."""

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

    async def run_once(self) -> list[Incident]:
        """Execute one ingestion cycle. Returns newly persisted incidents."""
        s = self._settings
        log = logger.bind(workspace_id=s.azure_monitor_workspace_id)
        log.info("ingestion_cycle_start")

        new_incidents: list[Incident] = []

        async with self._session_factory() as session:
            try:
                async with AzureMonitorClient(workspace_id=s.azure_monitor_workspace_id) as monitor:
                    connector = IngestionConnector(session=session, monitor_client=monitor)
                    new_incidents = await connector.run(
                        lookback_minutes=s.ingestion_lookback_minutes
                    )

                await session.commit()
            except Exception:
                await session.rollback()
                raise

        log.info("ingestion_cycle_complete", new_incidents=len(new_incidents))
        return new_incidents

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
