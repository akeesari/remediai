from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.config import Settings, get_settings
from packages.agent_runtime.pipeline import build_pipeline
from packages.data_access.models.audit_log_orm import AuditLogOrm
from packages.data_access.models.incident_orm import IncidentOrm
from packages.domain.models.agent_state import IncidentState
from packages.domain.models.incident import Incident, IncidentStatus

logger = structlog.get_logger()


class AgentPipelineRunner:
    """Runs the LangGraph agent pipeline for a single incident.

    Responsibilities:
    - Mark incident as ``triaging`` before the pipeline starts.
    - Build the initial ``IncidentState`` from the ``Incident`` domain model.
    - Invoke the compiled pipeline.
    - Write each agent trace entry to the ``audit_log`` table.
    - Update ``incidents.priority`` and status from the final state.
    """

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None = None,
        pipeline: Any = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._pipeline = pipeline or build_pipeline(settings=self._settings)

    async def run(self, incident: Incident) -> IncidentState:
        log = logger.bind(incident_id=str(incident.id))
        log.info("pipeline_start", exception_type=incident.exception_type)

        await self._session.execute(
            update(IncidentOrm)
            .where(IncidentOrm.id == incident.id)
            .values(status=IncidentStatus.TRIAGING.value)
        )

        initial_state: IncidentState = {
            "incident_id": str(incident.id),
            "correlation_id": str(incident.correlation_id),
            "exception_type": incident.exception_type,
            "exception_message": incident.exception_message,
            "stack_trace": incident.stack_trace or "",
            "raw_payload": dict(incident.raw_payload),
            "agent_trace": [],
            "errors": [],
            "triage_labels": [],
        }

        final_state: IncidentState = await self._pipeline.ainvoke(initial_state)

        await self._persist_agent_trace(final_state, incident)
        await self._update_incident(final_state, incident)
        await self._session.flush()

        log.info(
            "pipeline_complete",
            priority=final_state.get("priority"),
            labels=final_state.get("triage_labels"),
            errors=len(final_state.get("errors", [])),
        )
        return final_state

    async def _persist_agent_trace(
        self,
        state: IncidentState,
        incident: Incident,
    ) -> None:
        for entry in state.get("agent_trace", []):
            orm = AuditLogOrm(
                id=uuid4(),
                incident_id=incident.id,
                agent_name=str(entry.get("agent_name", "unknown")),
                action="agent_run",
                actor_identity="system",
                log_metadata={
                    "input_summary": entry.get("input_summary"),
                    "output_summary": entry.get("output_summary"),
                    "prompt_version": entry.get("prompt_version"),
                    "latency_ms": entry.get("latency_ms"),
                    "error": entry.get("error"),
                },
                timestamp=datetime.now(UTC),
            )
            self._session.add(orm)

    async def _update_incident(
        self,
        state: IncidentState,
        incident: Incident,
    ) -> None:
        priority = state.get("priority") or incident.priority.value
        has_errors = bool(state.get("errors"))
        new_status = (
            IncidentStatus.ANALYSIS_FAILED.value if has_errors else IncidentStatus.TRIAGING.value
        )
        await self._session.execute(
            update(IncidentOrm)
            .where(IncidentOrm.id == incident.id)
            .values(priority=priority, status=new_status)
        )
