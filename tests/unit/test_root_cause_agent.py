"""Unit tests for the root cause agent node — LLM is mocked throughout."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage

from packages.agent_runtime.root_cause.agent import AGENT_NAME, PROMPT_VERSION, make_root_cause_node
from packages.domain.models.agent_state import IncidentState

_RC_VALID = json.dumps(
    {
        "root_cause_summary": "Null reference in UserService.GetById when DB returns null.",
        "root_cause_json": {
            "component": "UserService.GetById",
            "likely_cause": "Missing null guard after repository call.",
            "contributing_factors": ["No null check", "Unvalidated assumption"],
            "confidence": 0.85,
        },
        "evidence": ["Top frame points to UserService.GetById"],
    }
)


def _make_llm(json_response: str) -> MagicMock:
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content=json_response))
    return llm


def _make_state(**overrides: object) -> IncidentState:
    base: IncidentState = {
        "incident_id": "test-rc-001",
        "correlation_id": "corr-rc-001",
        "exception_type": "System.NullReferenceException",
        "exception_message": "Object reference not set to an instance of an object.",
        "stack_trace": "   at UserService.GetById(Int32 id) in UserService.cs:line 42",
        "raw_payload": {},
        "agent_trace": [],
        "errors": [],
        "triage_labels": ["null-reference"],
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


class TestRootCauseNodeLLMPath:
    @pytest.mark.asyncio
    async def test_calls_llm(self) -> None:
        llm = _make_llm(_RC_VALID)
        node = make_root_cause_node(llm)
        await node(_make_state())
        llm.ainvoke.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_summary_and_json(self) -> None:
        llm = _make_llm(_RC_VALID)
        node = make_root_cause_node(llm)
        result = await node(_make_state())
        assert (
            result["root_cause_summary"]
            == "Null reference in UserService.GetById when DB returns null."
        )
        assert result["root_cause_json"]["component"] == "UserService.GetById"
        assert result["root_cause_json"]["confidence"] == 0.85

    @pytest.mark.asyncio
    async def test_appends_trace_entry(self) -> None:
        llm = _make_llm(_RC_VALID)
        node = make_root_cause_node(llm)
        result = await node(_make_state())
        assert len(result["agent_trace"]) == 1
        entry = result["agent_trace"][0]
        assert entry["agent_name"] == AGENT_NAME
        assert entry["error"] is None

    @pytest.mark.asyncio
    async def test_prompt_version_in_trace(self) -> None:
        llm = _make_llm(_RC_VALID)
        node = make_root_cause_node(llm)
        result = await node(_make_state())
        assert result["agent_trace"][0]["prompt_version"] == PROMPT_VERSION

    @pytest.mark.asyncio
    async def test_no_errors_on_clean_run(self) -> None:
        llm = _make_llm(_RC_VALID)
        node = make_root_cause_node(llm)
        result = await node(_make_state())
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_markdown_fences_stripped(self) -> None:
        fenced = f"```json\n{_RC_VALID}\n```"
        llm = _make_llm(fenced)
        node = make_root_cause_node(llm)
        result = await node(_make_state())
        assert result["root_cause_summary"] != ""
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_top_frames_sent_in_llm_call(self) -> None:
        llm = _make_llm(_RC_VALID)
        node = make_root_cause_node(llm)
        state = _make_state(
            stack_trace="   at UserService.GetById(Int32 id) in UserService.cs:line 42"
        )
        await node(state)
        messages = llm.ainvoke.call_args[0][0]
        human_content = messages[-1].content
        assert "top_stack_frames" in human_content
        assert "UserService.GetById" in human_content

    @pytest.mark.asyncio
    async def test_confidence_clamped_above_one(self) -> None:
        payload = json.dumps(
            {
                "root_cause_summary": "Summary.",
                "root_cause_json": {
                    "component": "Svc",
                    "likely_cause": "cause",
                    "contributing_factors": [],
                    "confidence": 1.5,
                },
                "evidence": [],
            }
        )
        llm = _make_llm(payload)
        node = make_root_cause_node(llm)
        result = await node(_make_state())
        assert result["root_cause_json"]["confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_confidence_clamped_below_zero(self) -> None:
        payload = json.dumps(
            {
                "root_cause_summary": "Summary.",
                "root_cause_json": {
                    "component": "Svc",
                    "likely_cause": "cause",
                    "contributing_factors": [],
                    "confidence": -0.3,
                },
                "evidence": [],
            }
        )
        llm = _make_llm(payload)
        node = make_root_cause_node(llm)
        result = await node(_make_state())
        assert result["root_cause_json"]["confidence"] >= 0.0


class TestRootCauseNodeFailurePath:
    @pytest.mark.asyncio
    async def test_llm_failure_returns_default_summary(self) -> None:
        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
        node = make_root_cause_node(llm)
        result = await node(_make_state())
        assert "manual review" in result["root_cause_summary"]
        assert result["root_cause_json"]["likely_cause"] == "insufficient_evidence"
        assert result["root_cause_json"]["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_llm_failure_appends_error(self) -> None:
        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=RuntimeError("timeout"))
        node = make_root_cause_node(llm)
        result = await node(_make_state())
        assert len(result["errors"]) == 1
        assert "timeout" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_llm_failure_trace_records_error(self) -> None:
        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=RuntimeError("connection refused"))
        node = make_root_cause_node(llm)
        result = await node(_make_state())
        assert result["agent_trace"][0]["error"] is not None
        assert "connection refused" in result["agent_trace"][0]["error"]


class TestRootCauseNodeStateIntegration:
    @pytest.mark.asyncio
    async def test_existing_trace_preserved(self) -> None:
        existing = [{"agent_name": "triage", "output_summary": "priority=high"}]
        state = _make_state(agent_trace=existing)
        llm = _make_llm(_RC_VALID)
        node = make_root_cause_node(llm)
        result = await node(state)
        assert len(result["agent_trace"]) == 2
        assert result["agent_trace"][0]["agent_name"] == "triage"
        assert result["agent_trace"][1]["agent_name"] == AGENT_NAME

    @pytest.mark.asyncio
    async def test_existing_errors_preserved_on_new_error(self) -> None:
        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=RuntimeError("fail"))
        state = _make_state(errors=["prior-error"])
        node = make_root_cause_node(llm)
        result = await node(state)
        assert len(result["errors"]) == 2
        assert "prior-error" in result["errors"]

    @pytest.mark.asyncio
    async def test_empty_stack_trace_does_not_crash(self) -> None:
        llm = _make_llm(_RC_VALID)
        node = make_root_cause_node(llm)
        result = await node(_make_state(stack_trace=""))
        assert result["root_cause_summary"] != ""
