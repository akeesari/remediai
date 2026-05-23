from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

import structlog

from packages.agent_runtime.rag.models import RAGResult
from packages.domain.models.agent_state import IncidentState
from packages.domain.models.audit import AgentTraceEntry

logger = structlog.get_logger()

AGENT_NAME = "rag"

_SCORE_THRESHOLD = 0.6
_MAX_RESULTS = 5
_MAX_QUERY_LEN = 1000

# Lower number = higher priority
_SOURCE_PRIORITY: dict[str, int] = {
    "runbook": 0,
    "prior_fix": 1,
    "documentation": 2,
    "source_code": 3,
}


class SearchClientProtocol(Protocol):
    """Minimal interface required by the RAG agent."""

    async def search(self, query: str, top: int = 10) -> list[dict[str, Any]]: ...


def make_rag_node(
    search_client: SearchClientProtocol | None = None,
    settings: Any = None,
) -> Callable[[IncidentState], Awaitable[dict[str, Any]]]:
    """Return an async LangGraph node that retrieves RAG results from Azure AI Search."""

    async def rag_node(state: IncidentState) -> dict[str, Any]:
        start_ms = int(time.monotonic() * 1000)
        incident_id: str = state.get("incident_id", "")
        root_cause_summary: str = state.get("root_cause_summary", "") or ""
        exception_type: str = state.get("exception_type", "")
        triage_labels: list[str] = state.get("triage_labels", [])

        log = logger.bind(agent=AGENT_NAME, incident_id=incident_id)
        log.info("rag_start")

        client = _resolve_client(search_client, settings)
        error: str | None = None
        rag_results: list[RAGResult] = []

        try:
            query = _build_query(root_cause_summary, exception_type, triage_labels)
            raw_results = await client.search(query=query, top=_MAX_RESULTS * 2)
            rag_results = _process_results(raw_results)
            log.info("rag_complete", results_returned=len(rag_results))
        except Exception as exc:
            log.error("rag_failed", error=str(exc))
            error = str(exc)

        latency_ms = int(time.monotonic() * 1000) - start_ms
        trace_entry = AgentTraceEntry(
            agent_name=AGENT_NAME,
            prompt_version=None,
            input_summary=f"exception_type={exception_type}, labels={triage_labels}",
            output_summary=f"rag_results={len(rag_results)}",
            latency_ms=latency_ms,
            error=error,
        )

        existing_trace: list[dict[str, Any]] = list(state.get("agent_trace", []))
        existing_errors: list[str] = list(state.get("errors", []))
        if error:
            existing_errors.append(f"{AGENT_NAME}: {error}")

        return {
            "rag_results": [r.model_dump() for r in rag_results],
            "agent_trace": existing_trace + [trace_entry.model_dump()],
            "errors": existing_errors,
        }

    return rag_node


def _resolve_client(
    search_client: SearchClientProtocol | None,
    settings: Any,
) -> SearchClientProtocol:
    if search_client is not None:
        return search_client
    from apps.api.core.config import get_settings
    from packages.integrations.azure_search.client import AzureSearchClient

    s = settings or get_settings()
    return AzureSearchClient.from_settings(s)


def _build_query(
    root_cause_summary: str,
    exception_type: str,
    triage_labels: list[str],
) -> str:
    parts = [root_cause_summary, exception_type] + triage_labels
    query = " ".join(p for p in parts if p).strip()
    return query[:_MAX_QUERY_LEN]


def _process_results(raw: list[dict[str, Any]]) -> list[RAGResult]:
    mapped = [_map_result(r) for r in raw]
    valid = [r for r in mapped if r is not None and r.relevance_score > _SCORE_THRESHOLD]
    valid.sort(key=lambda r: (_SOURCE_PRIORITY.get(r.source, 99), -r.relevance_score))
    return valid[:_MAX_RESULTS]


def _map_result(raw: dict[str, Any]) -> RAGResult | None:
    score = float(raw.get("@search.score", 0.0))
    title = str(raw.get("title") or raw.get("name") or "Untitled")
    content = str(raw.get("content") or raw.get("excerpt") or raw.get("body") or "")
    source = str(raw.get("source_type") or raw.get("source") or "documentation")
    raw_url = raw.get("url") or raw.get("path")
    url = str(raw_url) if raw_url else None
    return RAGResult(
        source=source,
        title=title,
        excerpt=content[:500],
        relevance_score=score,
        url=url,
    )
