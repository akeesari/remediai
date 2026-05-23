from __future__ import annotations

import json
import time
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from packages.agent_runtime.triage.models import TriageOutput
from packages.agent_runtime.triage.prompt import load_triage_prompt
from packages.agent_runtime.triage.rules import apply_rules
from packages.domain.models.agent_state import IncidentState
from packages.domain.models.audit import AgentTraceEntry

logger = structlog.get_logger()

AGENT_NAME = "triage"
PROMPT_VERSION = "triage_v1"


def make_triage_node(
    llm: BaseChatModel,
) -> Callable[[IncidentState], Awaitable[dict[str, Any]]]:
    """Return an async LangGraph node function with the LLM injected."""

    async def triage_node(state: IncidentState) -> dict[str, Any]:
        start_ms = int(time.monotonic() * 1000)
        exception_type: str = state.get("exception_type", "")
        exception_message: str = state.get("exception_message", "")
        incident_id: str = state.get("incident_id", "")

        log = logger.bind(agent=AGENT_NAME, incident_id=incident_id)
        log.info("triage_start", exception_type=exception_type)

        error: str | None = None
        prompt_version: str | None = None
        rule_match = apply_rules(exception_type)

        if rule_match.matched:
            output = TriageOutput(
                priority=rule_match.priority,
                triage_labels=rule_match.labels,
                rationale=f"Rule match for {exception_type}.",
                confidence=1.0,
            )
            log.info("triage_rule_matched", labels=rule_match.labels, priority=rule_match.priority)
        else:
            prompt_version = PROMPT_VERSION
            try:
                output = await _call_llm(llm, state)
                log.info(
                    "triage_llm_complete",
                    priority=output.priority,
                    labels=output.triage_labels,
                    confidence=output.confidence,
                )
            except Exception as exc:
                log.error("triage_llm_failed", error=str(exc))
                error = str(exc)
                output = TriageOutput(
                    priority="medium",
                    triage_labels=["unknown"],
                    rationale="LLM call failed; default triage applied.",
                    confidence=0.0,
                )

        latency_ms = int(time.monotonic() * 1000) - start_ms
        trace_entry = AgentTraceEntry(
            agent_name=AGENT_NAME,
            prompt_version=prompt_version,
            input_summary=f"type={exception_type}, msg={exception_message[:100]}",
            output_summary=f"priority={output.priority}, labels={output.triage_labels}",
            latency_ms=latency_ms,
            error=error,
        )

        existing_trace: list[dict[str, Any]] = list(state.get("agent_trace", []))
        existing_errors: list[str] = list(state.get("errors", []))
        if error:
            existing_errors.append(f"{AGENT_NAME}: {error}")

        return {
            "priority": output.priority,
            "triage_labels": output.triage_labels,
            "group_id": output.group_id,
            "agent_trace": existing_trace + [trace_entry.model_dump()],
            "errors": existing_errors,
        }

    return triage_node


async def _call_llm(llm: BaseChatModel, state: IncidentState) -> TriageOutput:
    system_prompt = load_triage_prompt()
    user_content = json.dumps(
        {
            "incident_id": state.get("incident_id", ""),
            "exception_type": state.get("exception_type", ""),
            "exception_message": state.get("exception_message", ""),
            "stack_trace": (state.get("stack_trace", "") or "")[:2000],
            "recent_incident_signatures": [],
        },
        ensure_ascii=False,
    )

    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_content)]
    response = await llm.ainvoke(messages)

    content = str(response.content).strip()
    # Strip markdown code fences if the model wraps its output
    if content.startswith("```"):
        parts = content.split("```")
        content = parts[1] if len(parts) > 1 else content
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    data: dict[str, Any] = json.loads(content)
    return TriageOutput.model_validate(data)
