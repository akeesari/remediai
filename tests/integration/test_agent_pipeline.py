"""End-to-end pipeline tests — LangGraph pipeline compiled with mocked LLM."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage

from packages.agent_runtime.pipeline import build_pipeline
from packages.domain.models.agent_state import IncidentState

# ---- Default LLM response payloads ----------------------------------------

_TRIAGE_JSON = json.dumps(
    {
        "priority": "high",
        "triage_labels": ["generic-error"],
        "group_id": None,
        "rationale": "No rule matched.",
        "confidence": 0.7,
    }
)

_RC_JSON = json.dumps(
    {
        "root_cause_summary": "Null reference in service layer when DB returns null.",
        "root_cause_json": {
            "component": "TestService.Process",
            "likely_cause": "Unguarded null return from repository.",
            "contributing_factors": ["Missing null check"],
            "confidence": 0.75,
        },
        "evidence": ["Top frame points to service layer"],
    }
)


def _mock_llm(response_json: str = "") -> MagicMock:
    """Single-response mock — suited for tests where only one LLM call occurs."""
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content=response_json or _RC_JSON))
    return llm


def _mock_llm_sequence(*responses: str) -> MagicMock:
    """Multi-response mock — each call returns the next item in *responses*."""
    llm = MagicMock()
    llm.ainvoke = AsyncMock(side_effect=[AIMessage(content=r) for r in responses])
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
    async def test_pipeline_runs_both_nodes(self) -> None:
        """Full pipeline produces priority (triage) and root_cause_summary."""
        pipeline = build_pipeline(llm=_mock_llm())
        result: IncidentState = await pipeline.ainvoke(_make_initial_state())

        assert result.get("priority") is not None
        assert isinstance(result.get("triage_labels"), list)
        assert result.get("root_cause_summary") is not None

    @pytest.mark.asyncio
    async def test_triage_rule_path_skips_triage_llm(self) -> None:
        """When a triage rule matches, triage skips LLM; root_cause still calls it once."""
        llm = _mock_llm()
        pipeline = build_pipeline(llm=llm)

        result: IncidentState = await pipeline.ainvoke(
            _make_initial_state(exception_type="System.NullReferenceException")
        )

        llm.ainvoke.assert_awaited_once()  # only root_cause called LLM
        assert result["priority"] == "high"
        assert "null-reference" in result["triage_labels"]

    @pytest.mark.asyncio
    async def test_llm_path_called_for_unknown_exception(self) -> None:
        """Both triage and root_cause call LLM when no rule matches."""
        llm = _mock_llm_sequence(_TRIAGE_JSON, _RC_JSON)
        pipeline = build_pipeline(llm=llm)

        await pipeline.ainvoke(
            _make_initial_state(exception_type="MyApp.CompletelyUnknownException")
        )

        assert llm.ainvoke.await_count == 2

    @pytest.mark.asyncio
    async def test_agent_trace_has_two_entries(self) -> None:
        pipeline = build_pipeline(llm=_mock_llm())
        result: IncidentState = await pipeline.ainvoke(_make_initial_state())

        trace = result.get("agent_trace", [])
        assert len(trace) == 2
        assert trace[0]["agent_name"] == "triage"
        assert trace[1]["agent_name"] == "root_cause"
        assert all("latency_ms" in e for e in trace)

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
    async def test_both_llm_agents_fail_gracefully(self) -> None:
        """Triage and root_cause LLM calls fail; defaults applied; 2 errors recorded."""
        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=RuntimeError("Azure OpenAI unavailable"))
        pipeline = build_pipeline(llm=llm)

        result: IncidentState = await pipeline.ainvoke(
            _make_initial_state(exception_type="Unknown.Error")
        )

        assert result["priority"] == "medium"
        assert "unknown" in result["triage_labels"]
        assert len(result.get("errors", [])) == 2

    @pytest.mark.asyncio
    async def test_root_cause_json_in_final_state(self) -> None:
        pipeline = build_pipeline(llm=_mock_llm())
        result: IncidentState = await pipeline.ainvoke(_make_initial_state())

        rc = result.get("root_cause_json")
        assert rc is not None
        assert "component" in rc
        assert "confidence" in rc
