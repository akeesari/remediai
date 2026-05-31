from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from packages.agent_runtime.language_detector import detect_language
from packages.agent_runtime.pipeline import build_pipeline
from packages.config.settings import Settings, get_settings
from packages.data_access.models.analysis_orm import AnalysisOrm
from packages.data_access.models.audit_log_orm import AuditLogOrm
from packages.data_access.models.incident_orm import IncidentOrm
from packages.data_access.models.work_item_orm import WorkItemOrm
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

        # Load ORM with relationships
        stmt = (
            select(IncidentOrm)
            .where(IncidentOrm.id == incident.id)
            .options(
                selectinload(IncidentOrm.analyses),
                selectinload(IncidentOrm.work_items),
            )
        )
        res = await self._session.execute(stmt)
        orm = res.scalar_one_or_none()

        if (
            orm
            and orm.status == IncidentStatus.ANALYZED.value
            and orm.approval_status == "approved"
        ):
            # Running approved PR + validation agents path
            log.info("pipeline_approved_path", note="running PR and validation agents")

            # Update status to triaging during run
            orm.status = IncidentStatus.TRIAGING.value
            await self._session.flush()

            analysis = orm.analyses[0] if orm.analyses else None
            work_item = orm.work_items[0] if orm.work_items else None

            lang = detect_language(incident.exception_type, incident.stack_trace or "")
            initial_state: IncidentState = {
                "incident_id": str(incident.id),
                "correlation_id": str(incident.correlation_id),
                "exception_type": incident.exception_type,
                "exception_message": incident.exception_message,
                "stack_trace": incident.stack_trace or "",
                "raw_payload": dict(incident.raw_payload),
                "exception_language": lang,
                "agent_trace": list(analysis.agent_trace)
                if (analysis and analysis.agent_trace)
                else [],
                "errors": [],
                "triage_labels": [],
                "priority": orm.priority,
                "approval_status": orm.approval_status,
                "approved_recommendation_rank": orm.approved_recommendation_rank,
                "root_cause_summary": analysis.root_cause if analysis else None,
                "root_cause_json": analysis.root_cause_json if analysis else None,
                "recommendations": analysis.recommendations if analysis else [],
                "code_snippets": analysis.code_snippets if analysis else [],
                "rag_results": analysis.rag_results if analysis else [],
            }
            if work_item:
                initial_state["ado_bug_id"] = work_item.ado_item_id
                initial_state["ado_bug_url"] = work_item.ado_item_url

            from packages.agent_runtime.pr_agent.agent import make_pr_agent_node
            from packages.agent_runtime.validation_agent.agent import make_validation_agent_node
            from packages.integrations.providers.registry import (
                create_chat_model,
                ensure_valid_provider_config,
            )

            ensure_valid_provider_config(self._settings)
            llm = create_chat_model(self._settings)

            pr_node = make_pr_agent_node(settings=self._settings)
            val_node = make_validation_agent_node(llm=llm, settings=self._settings)

            orig_trace_len = len(initial_state["agent_trace"])

            # Invoke nodes
            pr_res = await pr_node(initial_state)
            initial_state.update(cast(IncidentState, pr_res))

            val_res = await val_node(initial_state)
            initial_state.update(cast(IncidentState, val_res))

            final_state = initial_state

            # Persist the new agent traces to audit logs
            new_trace_entries = final_state.get("agent_trace", [])[orig_trace_len:]
            for entry in new_trace_entries:
                audit_orm = AuditLogOrm(
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
                self._session.add(audit_orm)

            # Update WorkItemOrm with PR details
            if work_item and final_state.get("pr_url"):
                work_item.pr_url = final_state.get("pr_url")
                work_item.pr_branch = final_state.get("pr_branch")
                self._session.add(work_item)

            # Update AnalysisOrm trace
            if analysis:
                analysis.agent_trace = _to_json_compatible(final_state.get("agent_trace", []))
                self._session.add(analysis)

            # Update Incident status
            has_errors = bool(final_state.get("errors"))
            orm.status = (
                IncidentStatus.ANALYSIS_FAILED.value
                if has_errors
                else IncidentStatus.PR_CREATED.value
            )
            await self._session.flush()

            log.info(
                "pipeline_approved_path_complete",
                pr_url=final_state.get("pr_url"),
                errors=len(final_state.get("errors", [])),
            )
            return final_state

        else:
            await self._session.execute(
                update(IncidentOrm)
                .where(IncidentOrm.id == incident.id)
                .values(status=IncidentStatus.TRIAGING.value)
            )

            initial_state = IncidentState(
                incident_id=str(incident.id),
                correlation_id=str(incident.correlation_id),
                exception_type=incident.exception_type,
                exception_message=incident.exception_message,
                stack_trace=incident.stack_trace or "",
                raw_payload=dict(incident.raw_payload),
                exception_language=detect_language(
                    incident.exception_type, incident.stack_trace or ""
                ),
                agent_trace=[],
                errors=[],
                triage_labels=[],
            )

            final_state = cast(IncidentState, await self._pipeline.ainvoke(initial_state))

            await self._persist_agent_trace(final_state, incident)
            await self._update_incident(final_state, incident)
            await self._persist_analysis_and_work_item(final_state, incident)
            await self._session.flush()

            rc_json = final_state.get("root_cause_json") or {}
            log.info(
                "pipeline_complete",
                priority=final_state.get("priority"),
                labels=final_state.get("triage_labels"),
                root_cause_component=rc_json.get("component"),
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
            IncidentStatus.ANALYSIS_FAILED.value if has_errors else IncidentStatus.ANALYZED.value
        )
        await self._session.execute(
            update(IncidentOrm)
            .where(IncidentOrm.id == incident.id)
            .values(priority=priority, status=new_status)
        )

    async def _persist_analysis_and_work_item(
        self,
        state: IncidentState,
        incident: Incident,
    ) -> None:
        analysis = AnalysisOrm(
            id=uuid4(),
            incident_id=incident.id,
            root_cause=state.get("root_cause_summary"),
            root_cause_json=_to_json_compatible(state.get("root_cause_json") or {}),
            recommendations=list(_to_json_compatible(state.get("recommendations") or [])),
            code_snippets=list(_to_json_compatible(state.get("code_snippets") or [])),
            rag_results=list(_to_json_compatible(state.get("rag_results") or [])),
            agent_trace=list(_to_json_compatible(state.get("agent_trace") or [])),
            created_at=datetime.now(UTC),
        )
        self._session.add(analysis)

        ado_bug_id = state.get("ado_bug_id")
        ado_bug_url = state.get("ado_bug_url")
        if ado_bug_id is not None:
            try:
                ado_item_id = int(ado_bug_id)
            except (ValueError, TypeError):
                ado_item_id = 0
            work_item = WorkItemOrm(
                id=uuid4(),
                incident_id=incident.id,
                item_type="bug",
                ado_item_id=ado_item_id,
                ado_item_url=str(ado_bug_url or ""),
                created_at=datetime.now(UTC),
            )
            self._session.add(work_item)


def _to_json_compatible(value: Any) -> Any:
    """Convert nested values (e.g. datetimes) into JSON-compatible structures."""
    return json.loads(json.dumps(value, default=str))
