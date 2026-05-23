"""End-to-end pipeline tests — LangGraph pipeline compiled with mocked LLM."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage

from packages.agent_runtime.pipeline import build_pipeline
from packages.domain.models.agent_state import IncidentState

# ---- Default LLM response payload -------------------------------------------

_TRIAGE_JSON = json.dumps(
    {
        "priority": "high",
        "triage_labels": ["generic-error"],
        "group_id": None,
        "rationale": "No rule matched.",
        "confidence": 0.7,
    }
)


def _mock_llm(response_json: str = "") -> MagicMock:
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content=response_json or _TRIAGE_JSON))
    return llm


def _make_initial_state(**overrides: object) -> IncidentState:
    base: IncidentState = {
        "incident_id": "pipeline-test-001",
        "correlation_id": "corr-pipeline",
        "exception_type": "System.NullReferenceException",
        "exception_message": "Object reference not set to an instance of an object.",
        "stack_trace": "at OrderService.Process() in OrderService.cs:line 100",
        "raw_payload": {},
        "agent_trace": [],
        "errors": [],
        "triage_labels": [],
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


class TestPipelineEndToEnd:
    @pytest.mark.asyncio
    async def test_pipeline_runs_triage_node(self) -> None:
        """Pipeline produces priority and triage_labels."""
        pipeline = build_pipeline(llm=_mock_llm())
        result: IncidentState = await pipeline.ainvoke(_make_initial_state())

        assert result.get("priority") is not None
        assert isinstance(result.get("triage_labels"), list)

    @pytest.mark.asyncio
    async def test_triage_rule_path_skips_llm(self) -> None:
        """When a triage rule matches, LLM is never called."""
        llm = _mock_llm()
        pipeline = build_pipeline(llm=llm)

        result: IncidentState = await pipeline.ainvoke(
            _make_initial_state(exception_type="System.NullReferenceException")
        )

        llm.ainvoke.assert_not_called()
        assert result["priority"] == "high"
        assert "null-reference" in result["triage_labels"]

    @pytest.mark.asyncio
    async def test_llm_path_called_for_unknown_exception(self) -> None:
        """Triage calls LLM when no rule matches."""
        llm = _mock_llm()
        pipeline = build_pipeline(llm=llm)

        await pipeline.ainvoke(
            _make_initial_state(exception_type="MyApp.CompletelyUnknownException")
        )

        llm.ainvoke.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_agent_trace_has_one_entry(self) -> None:
        pipeline = build_pipeline(llm=_mock_llm())
        result: IncidentState = await pipeline.ainvoke(_make_initial_state())

        trace = result.get("agent_trace", [])
        assert len(trace) == 1
        assert trace[0]["agent_name"] == "triage"
        assert "latency_ms" in trace[0]

    @pytest.mark.asyncio
    async def test_critical_exception_priority_in_final_state(self) -> None:
        pipeline = build_pipeline(llm=_mock_llm())
        result: IncidentState = await pipeline.ainvoke(
            _make_initial_state(exception_type="System.OutOfMemoryException")
        )
        assert result["priority"] == "critical"
        assert "resource-exhaustion" in result["triage_labels"]

    @pytest.mark.asyncio
    async def test_errors_empty_on_clean_run(self) -> None:
        pipeline = build_pipeline(llm=_mock_llm())
        result: IncidentState = await pipeline.ainvoke(_make_initial_state())
        assert result.get("errors", []) == []

    @pytest.mark.asyncio
    async def test_llm_failure_gracefully_recorded(self) -> None:
        """Triage LLM fails for unknown exception; error recorded, defaults applied."""
        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=RuntimeError("Azure OpenAI unavailable"))
        pipeline = build_pipeline(llm=llm)

        result: IncidentState = await pipeline.ainvoke(
            _make_initial_state(exception_type="Unknown.Error")
        )

        assert result["priority"] == "medium"
        assert "unknown" in result["triage_labels"]
        assert len(result.get("errors", [])) == 1
