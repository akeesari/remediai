"""Unit tests for the triage agent node — LLM is mocked throughout."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage

from packages.agent_runtime.triage.agent import make_triage_node
from packages.domain.models.agent_state import IncidentState


def _make_state(**overrides: object) -> IncidentState:
    base: IncidentState = {
        "incident_id": "test-incident-001",
        "correlation_id": "corr-001",
        "exception_type": "System.NullReferenceException",
        "exception_message": "Object reference not set to an instance of an object.",
        "stack_trace": "   at UserService.GetById(int id) in UserService.cs:line 42",
        "raw_payload": {},
        "agent_trace": [],
        "errors": [],
        "triage_labels": [],
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


def _make_llm(json_response: str) -> MagicMock:
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content=json_response))
    return llm


class TestTriageNodeRulePath:
    """When a rule matches, the LLM must never be called."""

    @pytest.mark.asyncio
    async def test_null_reference_uses_rule(self) -> None:
        llm = MagicMock()
        node = make_triage_node(llm)
        state = _make_state(exception_type="System.NullReferenceException")

        result = await node(state)

        assert result["priority"] == "high"
        assert "null-reference" in result["triage_labels"]
        llm.ainvoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_timeout_exception_uses_rule(self) -> None:
        llm = MagicMock()
        node = make_triage_node(llm)
        state = _make_state(exception_type="System.TimeoutException")

        result = await node(state)

        assert result["priority"] == "high"
        assert "timeout" in result["triage_labels"]
        llm.ainvoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_critical_exception_uses_rule(self) -> None:
        llm = MagicMock()
        node = make_triage_node(llm)
        state = _make_state(exception_type="System.OutOfMemoryException")

        result = await node(state)

        assert result["priority"] == "critical"
        llm.ainvoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_rule_path_appends_trace_entry(self) -> None:
        llm = MagicMock()
        node = make_triage_node(llm)
        state = _make_state(exception_type="System.NullReferenceException")

        result = await node(state)

        assert len(result["agent_trace"]) == 1
        entry = result["agent_trace"][0]
        assert entry["agent_name"] == "triage"
        assert entry["error"] is None

    @pytest.mark.asyncio
    async def test_rule_path_no_errors(self) -> None:
        llm = MagicMock()
        node = make_triage_node(llm)
        result = await node(_make_state(exception_type="System.NullReferenceException"))
        assert result["errors"] == []


class TestTriageNodeLLMPath:
    """When no rule matches, the LLM is called and its response is parsed."""

    @pytest.mark.asyncio
    async def test_unknown_exception_calls_llm(self) -> None:
        llm = _make_llm(
            '{"priority": "high", "triage_labels": ["custom-error"], '
            '"group_id": null, "rationale": "Custom domain error.", "confidence": 0.8}'
        )
        node = make_triage_node(llm)
        state = _make_state(exception_type="MyApp.CustomDomainException")

        result = await node(state)

        llm.ainvoke.assert_awaited_once()
        assert result["priority"] == "high"
        assert "custom-error" in result["triage_labels"]

    @pytest.mark.asyncio
    async def test_llm_response_with_markdown_fences_parsed(self) -> None:
        json_body = (
            '{"priority": "medium", "triage_labels": ["unknown-error"], '
            '"group_id": null, "rationale": "No pattern.", "confidence": 0.5}'
        )
        llm = _make_llm(f"```json\n{json_body}\n```")
        node = make_triage_node(llm)

        result = await node(_make_state(exception_type="Totally.Unknown.Error"))

        assert result["priority"] == "medium"
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_invalid_priority_from_llm_normalised_to_medium(self) -> None:
        llm = _make_llm(
            '{"priority": "EXTREME", "triage_labels": ["something"], '
            '"group_id": null, "rationale": "X", "confidence": 0.9}'
        )
        node = make_triage_node(llm)
        result = await node(_make_state(exception_type="Unknown.Error"))
        assert result["priority"] == "medium"

    @pytest.mark.asyncio
    async def test_llm_failure_returns_default_and_adds_error(self) -> None:
        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
        node = make_triage_node(llm)

        result = await node(_make_state(exception_type="Unknown.Error"))

        assert result["priority"] == "medium"
        assert "unknown" in result["triage_labels"]
        assert len(result["errors"]) == 1
        assert "LLM unavailable" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_llm_failure_trace_entry_records_error(self) -> None:
        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=RuntimeError("timeout"))
        node = make_triage_node(llm)

        result = await node(_make_state(exception_type="Unknown.Error"))

        assert result["agent_trace"][0]["error"] is not None
        assert "timeout" in result["agent_trace"][0]["error"]

    @pytest.mark.asyncio
    async def test_llm_path_prompt_version_in_trace(self) -> None:
        llm = _make_llm(
            '{"priority": "low", "triage_labels": ["misc"], '
            '"group_id": null, "rationale": "R", "confidence": 0.6}'
        )
        node = make_triage_node(llm)
        result = await node(_make_state(exception_type="Unknown.Error"))
        assert result["agent_trace"][0]["prompt_version"] == "triage_v1"


class TestTriageNodeStateIntegration:
    @pytest.mark.asyncio
    async def test_existing_trace_entries_preserved(self) -> None:
        llm = MagicMock()
        existing = [{"agent_name": "pre-existing", "output_summary": "x"}]
        state = _make_state(
            exception_type="System.NullReferenceException", agent_trace=existing
        )
        node = make_triage_node(llm)

        result = await node(state)

        assert len(result["agent_trace"]) == 2
        assert result["agent_trace"][0]["agent_name"] == "pre-existing"
        assert result["agent_trace"][1]["agent_name"] == "triage"

    @pytest.mark.asyncio
    async def test_existing_errors_preserved_on_new_error(self) -> None:
        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=RuntimeError("fail"))
        state = _make_state(exception_type="Unknown.Error", errors=["prior-error"])
        node = make_triage_node(llm)

        result = await node(state)

        assert len(result["errors"]) == 2
        assert "prior-error" in result["errors"]
