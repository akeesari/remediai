from __future__ import annotations

import json
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from packages.domain.models.agent_state import IncidentState
from packages.domain.models.audit import AgentTraceEntry


def parse_llm_json_response(content: str) -> dict[str, Any]:
    """Strip optional markdown code fences and parse JSON from an LLM response."""
    text = content.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    result: dict[str, Any] = json.loads(text)
    return result


class _TraceCtx:
    """Mutable timer/error holder yielded by agent_trace_ctx."""

    def __init__(self, agent_name: str, state: IncidentState) -> None:
        self._agent_name = agent_name
        self._state = state
        self._start_ms = int(time.monotonic() * 1000)
        self.error: str | None = None

    def build(
        self,
        *,
        prompt_version: str | None,
        input_summary: str,
        output_summary: str,
        **extra: Any,
    ) -> dict[str, Any]:
        """Build the state-update dict including trace entry and errors list."""
        latency_ms = int(time.monotonic() * 1000) - self._start_ms
        trace_entry = AgentTraceEntry(
            agent_name=self._agent_name,
            prompt_version=prompt_version,
            input_summary=input_summary,
            output_summary=output_summary,
            latency_ms=latency_ms,
            error=self.error,
        )
        existing_trace: list[dict[str, Any]] = list(self._state.get("agent_trace", []))
        existing_errors: list[str] = list(self._state.get("errors", []))
        if self.error:
            existing_errors.append(f"{self._agent_name}: {self.error}")
        return {
            "agent_trace": existing_trace + [trace_entry.model_dump()],
            "errors": existing_errors,
            **extra,
        }


@contextmanager
def agent_trace_ctx(agent_name: str, state: IncidentState) -> Generator[_TraceCtx, None, None]:
    """Context manager that times a block and exposes a builder for the agent trace state update.

    Usage::

        with agent_trace_ctx(AGENT_NAME, state) as ctx:
            try:
                output = await _call_llm(...)
            except Exception as exc:
                ctx.error = str(exc)
                output = _DEFAULT_OUTPUT
            return ctx.build(
                prompt_version=PROMPT_VERSION,
                input_summary="...",
                output_summary="...",
                my_field=output.my_field,
            )
    """
    yield _TraceCtx(agent_name=agent_name, state=state)
