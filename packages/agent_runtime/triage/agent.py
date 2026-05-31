from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from packages.agent_runtime.triage.models import TriageOutput
from packages.agent_runtime.triage.prompt import load_triage_prompt
from packages.agent_runtime.triage.rules import apply_rules
from packages.agent_runtime.utils import agent_trace_ctx, parse_llm_json_response
from packages.domain.models.agent_state import IncidentState
from packages.integrations.pii_scrubber import scrub

logger = structlog.get_logger()

AGENT_NAME = "triage"
PROMPT_VERSION = "triage_v2"


def make_triage_node(
    llm: BaseChatModel,
) -> Callable[[IncidentState], Awaitable[dict[str, Any]]]:
    """Return an async LangGraph node function with the LLM injected."""

    async def triage_node(state: IncidentState) -> dict[str, Any]:
        exception_type: str = state.get("exception_type", "")
        exception_message: str = state.get("exception_message", "")
        incident_id: str = state.get("incident_id", "")

        log = logger.bind(agent=AGENT_NAME, incident_id=incident_id)
        log.info("triage_start", exception_type=exception_type)

        prompt_version: str | None = None
        language: str = state.get("exception_language") or "unknown"
        rule_match = apply_rules(exception_type, language=language)

        with agent_trace_ctx(AGENT_NAME, state) as ctx:
            if rule_match.matched:
                output = TriageOutput(
                    priority=rule_match.priority,
                    triage_labels=rule_match.labels,
                    rationale=f"Rule match for {exception_type}.",
                    confidence=1.0,
                )
                log.info(
                    "triage_rule_matched", labels=rule_match.labels, priority=rule_match.priority
                )
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
                    ctx.error = str(exc)
                    output = TriageOutput(
                        priority="medium",
                        triage_labels=["unknown"],
                        rationale="LLM call failed; default triage applied.",
                        confidence=0.0,
                    )

            return ctx.build(
                prompt_version=prompt_version,
                input_summary=f"type={exception_type}, msg={scrub(exception_message)[:100]}",
                output_summary=f"priority={output.priority}, labels={output.triage_labels}",
                priority=output.priority,
                triage_labels=output.triage_labels,
                group_id=output.group_id,
            )

    return triage_node


async def _call_llm(llm: BaseChatModel, state: IncidentState) -> TriageOutput:
    system_prompt = load_triage_prompt()
    log = logger.bind(agent=AGENT_NAME, incident_id=state.get("incident_id", ""))
    log.debug("pii_scrub_applied", fields_scrubbed=["exception_message", "stack_trace"])
    user_content = json.dumps(
        {
            "incident_id": state.get("incident_id", ""),
            "exception_type": state.get("exception_type", ""),
            "exception_message": scrub(state.get("exception_message", "") or ""),
            "stack_trace": scrub((state.get("stack_trace", "") or "")[:2000]),
            "recent_incident_signatures": [],
        },
        ensure_ascii=False,
    )

    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_content)]
    response = await llm.ainvoke(messages)

    data = parse_llm_json_response(str(response.content))
    return TriageOutput.model_validate(data)
