from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

import structlog

from packages.agent_runtime.rag.models import RAGResult
from packages.agent_runtime.rag.query_builder import build_search_query
from packages.agent_runtime.rag.reranker import rerank
from packages.domain.models.agent_state import IncidentState
from packages.domain.models.audit import AgentTraceEntry

logger = structlog.get_logger()

AGENT_NAME = "rag"

_SCORE_THRESHOLD = 0.3  # Lowered to allow reranker to make final selection
_MAX_RAW_RESULTS = 10


class SearchClientProtocol(Protocol):
    """Minimal interface required by the RAG agent."""

    async def search(
        self,
        query: str,
        top: int = 10,
        *,
        vector_text: str | None = None,
        filter_expr: str | None = None,
    ) -> list[dict[str, Any]]: ...


def make_rag_node(
    search_client: SearchClientProtocol | None = None,
    settings: Any = None,
) -> Callable[[IncidentState], Awaitable[dict[str, Any]]]:
    """Return an async LangGraph node that retrieves RAG results from Azure AI Search."""

    async def rag_node(state: IncidentState) -> dict[str, Any]:
        start_ms = int(time.monotonic() * 1000)
        incident_id: str = state.get("incident_id", "")
        exception_type: str = state.get("exception_type", "")
        triage_labels: list[str] = state.get("triage_labels", [])

        log = logger.bind(agent=AGENT_NAME, incident_id=incident_id)
        log.info("rag_start")

        client = _resolve_client(search_client, settings)
        error: str | None = None
        rag_results: list[RAGResult] = []

        if client is None:
            log.info("rag_skipped", reason="search_not_configured")
        else:
            try:
                search_query = build_search_query(state)
                raw_results = await client.search(
                    query=search_query.text,
                    top=search_query.top,
                    vector_text=search_query.vector_text,
                    filter_expr=search_query.filter_expr,
                )
                candidates = _map_results(raw_results)
                rag_results = rerank(candidates, state)
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
) -> SearchClientProtocol | None:
    if search_client is not None:
        return search_client
    from packages.config.settings import get_settings
    from packages.integrations.azure_search.client import AzureSearchClient

    s = settings or get_settings()
    if not getattr(s, "azure_search_endpoint", ""):
        return None
    return AzureSearchClient.from_settings(s)


def _map_results(raw: list[dict[str, Any]]) -> list[RAGResult]:
    """Convert raw search dicts to RAGResult, filtering below score threshold."""
    results: list[RAGResult] = []
    for r in raw:
        mapped = _map_result(r)
        if mapped is not None and mapped.relevance_score > _SCORE_THRESHOLD:
            results.append(mapped)
    return results


def _map_result(raw: dict[str, Any]) -> RAGResult | None:
    score = float(raw.get("@search.score", 0.0))
    title = str(raw.get("title") or raw.get("name") or "Untitled")
    content = str(raw.get("content") or raw.get("excerpt") or raw.get("body") or "")
    source = str(raw.get("source_type") or raw.get("source") or "documentation")
    raw_url = raw.get("url") or raw.get("path")
    url = str(raw_url) if raw_url else None
    exception_type_raw = raw.get("exception_type")
    exception_type = str(exception_type_raw) if exception_type_raw else None
    return RAGResult(
        source=source,
        title=title,
        excerpt=content[:500],
        relevance_score=score,
        url=url,
        exception_type=exception_type,
    )
