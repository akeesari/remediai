from __future__ import annotations

import json
import time
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from packages.agent_runtime.root_cause.models import RootCauseJson, RootCauseOutput
from packages.agent_runtime.root_cause.prompt import load_root_cause_prompt
from packages.agent_runtime.root_cause.stack_parser import parse_stack_frames
from packages.domain.models.agent_state import IncidentState
from packages.domain.models.audit import AgentTraceEntry
from packages.integrations.pii_scrubber import scrub

logger = structlog.get_logger()

AGENT_NAME = "root_cause"
PROMPT_VERSION = "root_cause_v1"

_DEFAULT_OUTPUT = RootCauseOutput(
    root_cause_summary="Root cause analysis failed; manual review required.",
    root_cause_json=RootCauseJson(
        component="unknown",
        likely_cause="insufficient_evidence",
        contributing_factors=[],
        confidence=0.0,
    ),
    evidence=[],
)


def make_root_cause_node(
    llm: BaseChatModel,
) -> Callable[[IncidentState], Awaitable[dict[str, Any]]]:
    """Return an async LangGraph node that performs root cause analysis."""

    async def root_cause_node(state: IncidentState) -> dict[str, Any]:
        start_ms = int(time.monotonic() * 1000)
        exception_type: str = state.get("exception_type", "")
        exception_message: str = state.get("exception_message", "")
        stack_trace: str = state.get("stack_trace", "") or ""
        incident_id: str = state.get("incident_id", "")

        log = logger.bind(agent=AGENT_NAME, incident_id=incident_id)
        log.info("root_cause_start", exception_type=exception_type)

        frames = parse_stack_frames(stack_trace)
        top_frames = [f.method for f in frames]

        error: str | None = None
        try:
            output = await _call_llm(llm, state, top_frames)
            log.info(
                "root_cause_complete",
                component=output.root_cause_json.component,
                confidence=output.root_cause_json.confidence,
            )
        except Exception as exc:
            log.error("root_cause_llm_failed", error=str(exc))
            error = str(exc)
            output = _DEFAULT_OUTPUT

        latency_ms = int(time.monotonic() * 1000) - start_ms
        trace_entry = AgentTraceEntry(
            agent_name=AGENT_NAME,
            prompt_version=PROMPT_VERSION,
            input_summary=f"type={exception_type}, msg={scrub(exception_message)[:100]}, frames={len(top_frames)}",
            output_summary=f"component={output.root_cause_json.component}, confidence={output.root_cause_json.confidence}",
            latency_ms=latency_ms,
            error=error,
        )

        existing_trace: list[dict[str, Any]] = list(state.get("agent_trace", []))
        existing_errors: list[str] = list(state.get("errors", []))
        if error:
            existing_errors.append(f"{AGENT_NAME}: {error}")

        return {
            "root_cause_summary": output.root_cause_summary,
            "root_cause_json": output.root_cause_json.model_dump(),
            "agent_trace": existing_trace + [trace_entry.model_dump()],
            "errors": existing_errors,
        }

    return root_cause_node


async def _call_llm(
    llm: BaseChatModel,
    state: IncidentState,
    top_frames: list[str],
) -> RootCauseOutput:
    system_prompt = load_root_cause_prompt()
    log = logger.bind(agent=AGENT_NAME, incident_id=state.get("incident_id", ""))
    log.debug("pii_scrub_applied", fields_scrubbed=["exception_message", "stack_trace"])
    user_content = json.dumps(
        {
            "incident_id": state.get("incident_id", ""),
            "exception_type": state.get("exception_type", ""),
            "exception_message": scrub(state.get("exception_message", "") or ""),
            "stack_trace": scrub((state.get("stack_trace", "") or "")[:2000]),
            "triage_labels": state.get("triage_labels", []),
            "top_stack_frames": top_frames,
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
    return RootCauseOutput.model_validate(data)
