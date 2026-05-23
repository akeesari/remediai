"""Unit tests for the Fix Planner agent node — LLM is mocked throughout."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage

from packages.agent_runtime.fix_planner.agent import AGENT_NAME, make_fix_planner_node
from packages.domain.models.agent_state import IncidentState

_REC_JSON = json.dumps(
    {
        "recommendations": [
            {
                "rank": 1,
                "title": "Add null guard",
                "description": "Return 404 when user record is missing.",
                "affected_files": ["src/services/user_service.cs"],
                "suggested_change": "Add null check before mapping user entity.",
                "confidence": 0.88,
                "source_refs": ["runbook:null-pattern"],
            }
        ]
    }
)

_MULTI_REC_JSON = json.dumps(
    {
        "recommendations": [
            {
                "rank": 1,
                "title": "Low confidence fix",
                "description": "Desc A",
                "affected_files": [],
                "suggested_change": "Change A",
                "confidence": 0.4,
                "source_refs": [],
            },
            {
                "rank": 2,
                "title": "High confidence fix",
                "description": "Desc B",
                "affected_files": ["svc.cs"],
                "suggested_change": "Change B",
                "confidence": 0.9,
                "source_refs": ["runbook:x"],
            },
            {
                "rank": 3,
                "title": "Medium confidence fix",
                "description": "Desc C",
                "affected_files": [],
                "suggested_change": "Change C",
                "confidence": 0.7,
                "source_refs": [],
            },
        ]
    }
)


def _make_llm(response_json: str = "") -> MagicMock:
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content=response_json or _REC_JSON))
    return llm


def _make_state(**overrides: object) -> IncidentState:
    base: IncidentState = {
        "incident_id": "fix-test-001",
        "correlation_id": "corr-fix",
        "exception_type": "System.NullReferenceException",
        "exception_message": "Object reference not set.",
        "stack_trace": "",
        "raw_payload": {},
        "agent_trace": [],
        "errors": [],
        "triage_labels": ["null-reference"],
        "root_cause_summary": "Null reference in UserService.GetById when DB returns null.",
        "root_cause_json": {
            "component": "UserService.GetById",
            "likely_cause": "Unguarded null return from repository",
            "contributing_factors": ["Missing null check"],
            "confidence": 0.8,
        },
        "code_snippets": [],
        "rag_results": [],
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


class TestFixPlannerNodeHappyPath:
    @pytest.mark.asyncio
    async def test_llm_is_called(self) -> None:
        llm = _make_llm()
        node = make_fix_planner_node(llm=llm)
        await node(_make_state())
        llm.ainvoke.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_recommendations_returned(self) -> None:
        node = make_fix_planner_node(llm=_make_llm())
        result = await node(_make_state())
        assert len(result["recommendations"]) == 1
        assert result["recommendations"][0]["title"] == "Add null guard"

    @pytest.mark.asyncio
    async def test_no_errors_on_clean_run(self) -> None:
        node = make_fix_planner_node(llm=_make_llm())
        result = await node(_make_state())
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_trace_entry_appended(self) -> None:
        node = make_fix_planner_node(llm=_make_llm())
        result = await node(_make_state())
        assert len(result["agent_trace"]) == 1
        entry = result["agent_trace"][0]
        assert entry["agent_name"] == AGENT_NAME
        assert entry["prompt_version"] == "fix_planner_v1"
        assert entry["error"] is None

    @pytest.mark.asyncio
    async def test_recommendations_sorted_by_confidence_descending(self) -> None:
        node = make_fix_planner_node(llm=_make_llm(_MULTI_REC_JSON))
        result = await node(_make_state())
        confidences = [r["confidence"] for r in result["recommendations"]]
        assert confidences == sorted(confidences, reverse=True)

    @pytest.mark.asyncio
    async def test_recommendations_limited_to_three(self) -> None:
        many = json.dumps(
            {
                "recommendations": [
                    {
                        "rank": i + 1,
                        "title": f"Fix {i}",
                        "description": f"Desc {i}",
                        "affected_files": [],
                        "suggested_change": f"Change {i}",
                        "confidence": 0.5,
                        "source_refs": [],
                    }
                    for i in range(6)
                ]
            }
        )
        node = make_fix_planner_node(llm=_make_llm(many))
        result = await node(_make_state())
        assert len(result["recommendations"]) <= 3

    @pytest.mark.asyncio
    async def test_ranks_renumbered_after_sort(self) -> None:
        node = make_fix_planner_node(llm=_make_llm(_MULTI_REC_JSON))
        result = await node(_make_state())
        ranks = [r["rank"] for r in result["recommendations"]]
        assert ranks == list(range(1, len(ranks) + 1))

    @pytest.mark.asyncio
    async def test_markdown_fenced_json_parsed(self) -> None:
        fenced = f"```json\n{_REC_JSON}\n```"
        node = make_fix_planner_node(llm=_make_llm(fenced))
        result = await node(_make_state())
        assert len(result["recommendations"]) == 1

    @pytest.mark.asyncio
    async def test_confidence_clamped_above_one(self) -> None:
        overshoot = json.dumps(
            {
                "recommendations": [
                    {
                        "rank": 1,
                        "title": "Fix",
                        "description": "D",
                        "affected_files": [],
                        "suggested_change": "C",
                        "confidence": 1.5,
                        "source_refs": [],
                    }
                ]
            }
        )
        node = make_fix_planner_node(llm=_make_llm(overshoot))
        result = await node(_make_state())
        assert result["recommendations"][0]["confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_url_and_source_refs_preserved(self) -> None:
        node = make_fix_planner_node(llm=_make_llm())
        result = await node(_make_state())
        assert result["recommendations"][0]["source_refs"] == ["runbook:null-pattern"]

    @pytest.mark.asyncio
    async def test_existing_trace_preserved(self) -> None:
        existing: list[Any] = [{"agent_name": "rag", "output_summary": "rag_results=0"}]
        state = _make_state(agent_trace=existing)
        node = make_fix_planner_node(llm=_make_llm())
        result = await node(state)
        assert len(result["agent_trace"]) == 2
        assert result["agent_trace"][0]["agent_name"] == "rag"
        assert result["agent_trace"][1]["agent_name"] == AGENT_NAME


class TestFixPlannerNodeFailurePath:
    @pytest.mark.asyncio
    async def test_llm_failure_returns_default_recommendation(self) -> None:
        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
        node = make_fix_planner_node(llm=llm)
        result = await node(_make_state())
        assert len(result["recommendations"]) == 1
        assert "diagnostic evidence" in result["recommendations"][0]["title"].lower()

    @pytest.mark.asyncio
    async def test_llm_failure_appends_error(self) -> None:
        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=RuntimeError("timeout"))
        node = make_fix_planner_node(llm=llm)
        result = await node(_make_state())
        assert len(result["errors"]) == 1
        assert "timeout" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_llm_failure_trace_records_error(self) -> None:
        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=RuntimeError("network error"))
        node = make_fix_planner_node(llm=llm)
        result = await node(_make_state())
        assert result["agent_trace"][0]["error"] is not None

    @pytest.mark.asyncio
    async def test_existing_errors_preserved_on_new_error(self) -> None:
        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=RuntimeError("fail"))
        state = _make_state(errors=["prior-error"])
        node = make_fix_planner_node(llm=llm)
        result = await node(state)
        assert "prior-error" in result["errors"]
        assert len(result["errors"]) == 2

    @pytest.mark.asyncio
    async def test_default_recommendation_low_confidence(self) -> None:
        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=RuntimeError("fail"))
        node = make_fix_planner_node(llm=llm)
        result = await node(_make_state())
        assert result["recommendations"][0]["confidence"] < 0.5
