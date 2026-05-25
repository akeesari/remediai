"""Local-mode incident poller.

When LOCAL_MODE=true the worker skips Azure Monitor polling and instead
queries Postgres for incidents with status=new, then runs the agent pipeline
on each.  This processes exceptions detected by the log-bridge service.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.core.config import Settings, get_settings
from apps.worker.agents.runner import AgentPipelineRunner
from packages.data_access.models.incident_orm import IncidentOrm
from packages.domain.models.incident import Incident, IncidentPriority, IncidentStatus

logger = structlog.get_logger()

_BATCH_SIZE = 5


class LocalIncidentPoller:
    """Polls Postgres for new incidents and runs the LangGraph pipeline on each.

    Replaces IngestionScheduler when LOCAL_MODE=true.  Requires
    AZURE_OPENAI_ENDPOINT to be set for the pipeline to produce meaningful
    analysis; without it each run will fail gracefully and mark the incident
    as analysis_failed.
    """

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

    async def run_once(self) -> int:
        """Process one batch of new incidents. Returns the number processed."""
        # Phase 1: fetch IDs only — short-lived session, no locks held during processing
        async with self._session_factory() as session:
            stmt = (
                select(IncidentOrm.id)
                .where(IncidentOrm.status == IncidentStatus.NEW.value)
                .order_by(IncidentOrm.created_at.asc())
                .limit(_BATCH_SIZE)
            )
            result = await session.execute(stmt)
            incident_ids = list(result.scalars().all())

        if not incident_ids:
            return 0

        logger.info("local_poller_processing", batch_size=len(incident_ids))

        # Phase 2: process each incident in its own independent session
        processed = 0
        for inc_id in incident_ids:
            async with self._session_factory() as session:
                orm = await session.get(IncidentOrm, inc_id)
                if orm is None or orm.status != IncidentStatus.NEW.value:
                    continue  # already picked up by a concurrent run
                incident = _orm_to_domain(orm)
                try:
                    runner = AgentPipelineRunner(session=session, settings=self._settings)
                    await runner.run(incident)
                    await session.commit()
                    processed += 1
                    logger.info("local_poller_incident_done", incident_id=str(incident.id))
                except Exception as exc:
                    await session.rollback()
                    logger.error(
                        "local_poller_incident_failed",
                        incident_id=str(incident.id),
                        error=str(exc),
                    )

        return processed

    async def run_forever(self) -> None:
        interval = self._settings.local_incident_poll_interval_seconds
        logger.info("local_poller_start", poll_interval_seconds=interval)

        while True:
            try:
                processed = await self.run_once()
                if processed:
                    logger.info("local_poller_cycle_done", processed=processed)
            except Exception as exc:
                logger.error("local_poller_cycle_failed", error=str(exc))

            await asyncio.sleep(interval)


def _orm_to_domain(orm: IncidentOrm) -> Incident:
    return Incident(
        id=UUID(str(orm.id)),
        correlation_id=UUID(str(orm.correlation_id)),
        source=orm.source,
        exception_type=orm.exception_type,
        exception_message=orm.exception_message,
        stack_trace=orm.stack_trace,
        fingerprint=orm.fingerprint,
        priority=IncidentPriority(orm.priority),
        status=IncidentStatus(orm.status),
        raw_payload=dict(orm.raw_payload) if orm.raw_payload else {},
        created_at=orm.created_at if orm.created_at else datetime.now(UTC),
        updated_at=orm.updated_at if orm.updated_at else datetime.now(UTC),
    )
