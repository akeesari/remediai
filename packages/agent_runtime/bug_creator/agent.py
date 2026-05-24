from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

import structlog

from packages.agent_runtime.bug_creator.models import BugCreationResult
from packages.domain.models.agent_state import IncidentState
from packages.domain.models.audit import AgentTraceEntry

logger = structlog.get_logger()

AGENT_NAME = "bug_creator"

_DESCRIPTION_TEMPLATE = """\
<h2>Exception</h2>
<p><strong>{exception_type}</strong>: {exception_message}</p>

<h2>Root Cause</h2>
<p>{root_cause_summary}</p>
<ul>
  <li><strong>Component:</strong> {component}</li>
  <li><strong>Likely cause:</strong> {likely_cause}</li>
</ul>

<h2>Recommendations</h2>
{recommendations_html}
<h2>Triage</h2>
<p>Priority: {priority} | Labels: {labels}</p>

<h2>Analysis</h2>
<p>Incident ID: {incident_id}</p>
"""


class ADOBoardsClientProtocol(Protocol):
    """Minimal interface required by the bug_creator agent."""

    async def create_bug(
        self,
        title: str,
        description: str,
        priority: str,
        tags: str,
    ) -> dict[str, Any]: ...


def make_bug_creator_node(
    boards_client: ADOBoardsClientProtocol | None = None,
    settings: Any = None,
) -> Callable[[IncidentState], Awaitable[dict[str, Any]]]:
    """Return an async LangGraph node that creates an Azure DevOps Bug work item."""

    async def bug_creator_node(state: IncidentState) -> dict[str, Any]:
        start_ms = int(time.monotonic() * 1000)
        incident_id: str = state.get("incident_id", "")
        exception_type: str = state.get("exception_type", "")

        log = logger.bind(agent=AGENT_NAME, incident_id=incident_id)
        log.info("bug_creator_start", exception_type=exception_type)

        client = _resolve_client(boards_client, settings)
        error: str | None = None
        result: BugCreationResult | None = None

        if client is None:
            log.info("bug_creator_skipped", reason="no_boards_client_configured")
        else:
            try:
                title = _build_title(state)
                description = _build_description(state)
                priority: str = state.get("priority") or "medium"
                tags = ", ".join(state.get("triage_labels", []))

                raw = await client.create_bug(
                    title=title,
                    description=description,
                    priority=priority,
                    tags=tags,
                )
                bug_id = int(raw["id"])
                bug_url = str(raw.get("_links", {}).get("html", {}).get("href", ""))
                result = BugCreationResult(bug_id=bug_id, bug_url=bug_url, title=title)
                log.info("bug_creator_complete", bug_id=bug_id, bug_url=bug_url)
            except Exception as exc:
                log.error("bug_creator_failed", error=str(exc))
                error = str(exc)

        latency_ms = int(time.monotonic() * 1000) - start_ms
        trace_entry = AgentTraceEntry(
            agent_name=AGENT_NAME,
            prompt_version=None,
            input_summary=f"exception_type={exception_type}",
            output_summary=f"bug_id={result.bug_id if result else None}",
            latency_ms=latency_ms,
            error=error,
        )

        existing_trace: list[dict[str, Any]] = list(state.get("agent_trace", []))
        existing_errors: list[str] = list(state.get("errors", []))
        if error:
            existing_errors.append(f"{AGENT_NAME}: {error}")

        return {
            "ado_bug_id": result.bug_id if result else None,
            "ado_bug_url": result.bug_url if result else None,
            "agent_trace": existing_trace + [trace_entry.model_dump()],
            "errors": existing_errors,
        }

    return bug_creator_node


def _resolve_client(
    boards_client: ADOBoardsClientProtocol | None,
    settings: Any,
) -> ADOBoardsClientProtocol | None:
    if boards_client is not None:
        return boards_client
    from apps.api.core.config import get_settings
    from packages.integrations.azure_devops.boards_client import AzureDevOpsBoardsClient

    s = settings or get_settings()
    if not getattr(s, "azure_devops_org_url", ""):
        return None
    return AzureDevOpsBoardsClient.from_settings(s)


def _build_title(state: IncidentState) -> str:
    priority = (state.get("priority") or "medium").upper()
    exception_type = state.get("exception_type", "UnknownException")
    message = state.get("exception_message", "") or ""
    short_msg = message[:80].rstrip()
    if short_msg:
        return f"[{priority}] {exception_type}: {short_msg}"
    return f"[{priority}] {exception_type}"


def _build_description(state: IncidentState) -> str:
    rc_json: dict[str, Any] = state.get("root_cause_json") or {}
    recs: list[dict[str, Any]] = state.get("recommendations") or []

    recs_html = "".join(
        f"<li><strong>{r.get('title', '')}</strong>: {r.get('description', '')}</li>" for r in recs
    )
    recommendations_html = f"<ol>{recs_html}</ol>" if recs_html else "<p>None</p>"

    return _DESCRIPTION_TEMPLATE.format(
        exception_type=state.get("exception_type", ""),
        exception_message=state.get("exception_message", "") or "",
        root_cause_summary=state.get("root_cause_summary", "") or "",
        component=rc_json.get("component", "unknown"),
        likely_cause=rc_json.get("likely_cause", ""),
        recommendations_html=recommendations_html,
        priority=state.get("priority") or "medium",
        labels=", ".join(state.get("triage_labels", [])),
        incident_id=state.get("incident_id", ""),
    )
