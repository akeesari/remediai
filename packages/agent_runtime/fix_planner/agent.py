from __future__ import annotations

import json
import time
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from packages.agent_runtime.fix_planner.models import FixPlannerOutput, Recommendation
from packages.domain.models.agent_state import IncidentState
from packages.domain.models.audit import AgentTraceEntry
from packages.integrations.pii_scrubber import scrub

logger = structlog.get_logger()

AGENT_NAME = "fix_planner"
PROMPT_VERSION = "fix_planner_v1"

_MAX_RECOMMENDATIONS = 3
_MAX_SNIPPETS = 3
_MAX_RAG = 5

_DEFAULT_OUTPUT = FixPlannerOutput(
    recommendations=[
        Recommendation(
            rank=1,
            title="Gather more diagnostic evidence",
            description=(
                "Insufficient context to generate specific recommendations. "
                "Review logs, add instrumentation, and re-trigger analysis."
            ),
            affected_files=[],
            suggested_change=(
                "Add structured logging and correlation IDs to identify the failure path."
            ),
            confidence=0.3,
            source_refs=[],
        )
    ]
)


def _load_prompt() -> str:
    from packages.agent_runtime.prompt_registry import get_registry

    return get_registry().load("fix_planner", "1")


def make_fix_planner_node(
    llm: BaseChatModel,
) -> Callable[[IncidentState], Awaitable[dict[str, Any]]]:
    """Return an async LangGraph node that generates remediation recommendations."""

    async def fix_planner_node(state: IncidentState) -> dict[str, Any]:
        start_ms = int(time.monotonic() * 1000)
        incident_id: str = state.get("incident_id", "")
        root_cause_summary: str = state.get("root_cause_summary", "") or ""

        log = logger.bind(agent=AGENT_NAME, incident_id=incident_id)
        log.info("fix_planner_start")

        error: str | None = None
        try:
            output = await _call_llm(llm, state)
            output = _post_process(output)
            log.info("fix_planner_complete", recommendations=len(output.recommendations))
        except Exception as exc:
            log.error("fix_planner_failed", error=str(exc))
            error = str(exc)
            output = _DEFAULT_OUTPUT

        latency_ms = int(time.monotonic() * 1000) - start_ms
        trace_entry = AgentTraceEntry(
            agent_name=AGENT_NAME,
            prompt_version=PROMPT_VERSION,
            input_summary=f"root_cause={scrub(root_cause_summary)[:100]}",
            output_summary=f"recommendations={len(output.recommendations)}",
            latency_ms=latency_ms,
            error=error,
        )

        existing_trace: list[dict[str, Any]] = list(state.get("agent_trace", []))
        existing_errors: list[str] = list(state.get("errors", []))
        if error:
            existing_errors.append(f"{AGENT_NAME}: {error}")

        return {
            "recommendations": [r.model_dump() for r in output.recommendations],
            "agent_trace": existing_trace + [trace_entry.model_dump()],
            "errors": existing_errors,
        }

    return fix_planner_node


async def _call_llm(llm: BaseChatModel, state: IncidentState) -> FixPlannerOutput:
    system_prompt = _load_prompt()
    log = logger.bind(agent=AGENT_NAME, incident_id=state.get("incident_id", ""))
    log.debug("pii_scrub_applied", fields_scrubbed=["root_cause_summary"])
    user_content = json.dumps(
        {
            "incident_id": state.get("incident_id", ""),
            "root_cause_summary": scrub(state.get("root_cause_summary", "") or ""),
            "root_cause_json": state.get("root_cause_json") or {},
            "code_snippets": (state.get("code_snippets") or [])[:_MAX_SNIPPETS],
            "rag_results": (state.get("rag_results") or [])[:_MAX_RAG],
        },
        ensure_ascii=False,
    )

    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_content)]
    response = await llm.ainvoke(messages)

    content = str(response.content).strip()
    if content.startswith("```"):
        parts = content.split("```")
        content = parts[1] if len(parts) > 1 else content
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    data: dict[str, Any] = json.loads(content)
    return FixPlannerOutput.model_validate(data)


def _post_process(output: FixPlannerOutput) -> FixPlannerOutput:
    sorted_recs = sorted(output.recommendations, key=lambda r: -r.confidence)
    top = sorted_recs[:_MAX_RECOMMENDATIONS]
    renumbered = [Recommendation(**{**r.model_dump(), "rank": i + 1}) for i, r in enumerate(top)]
    return FixPlannerOutput(recommendations=renumbered)
