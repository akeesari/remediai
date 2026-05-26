from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from packages.agent_runtime.root_cause.models import RootCauseJson, RootCauseOutput
from packages.agent_runtime.root_cause.prompt import load_root_cause_prompt
from packages.agent_runtime.root_cause.stack_parser import parse_stack_frames
from packages.agent_runtime.utils import agent_trace_ctx, parse_llm_json_response
from packages.domain.models.agent_state import IncidentState
from packages.integrations.pii_scrubber import scrub

logger = structlog.get_logger()

AGENT_NAME = "root_cause"
PROMPT_VERSION = "root_cause_v2"

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
        exception_type: str = state.get("exception_type", "")
        exception_message: str = state.get("exception_message", "")
        stack_trace: str = state.get("stack_trace", "") or ""
        incident_id: str = state.get("incident_id", "")

        log = logger.bind(agent=AGENT_NAME, incident_id=incident_id)
        log.info("root_cause_start", exception_type=exception_type)

        frames = parse_stack_frames(stack_trace)
        top_frames = [f.method for f in frames]

        with agent_trace_ctx(AGENT_NAME, state) as ctx:
            try:
                output = await _call_llm(llm, state, top_frames)
                log.info(
                    "root_cause_complete",
                    component=output.root_cause_json.component,
                    confidence=output.root_cause_json.confidence,
                )
            except Exception as exc:
                log.error("root_cause_llm_failed", error=str(exc))
                ctx.error = str(exc)
                output = _DEFAULT_OUTPUT

            return ctx.build(
                prompt_version=PROMPT_VERSION,
                input_summary=f"type={exception_type}, msg={scrub(exception_message)[:100]}, frames={len(top_frames)}",
                output_summary=f"component={output.root_cause_json.component}, confidence={output.root_cause_json.confidence}",
                root_cause_summary=output.root_cause_summary,
                root_cause_json=output.root_cause_json.model_dump(),
            )

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

    data = parse_llm_json_response(str(response.content))
    return RootCauseOutput.model_validate(data)
