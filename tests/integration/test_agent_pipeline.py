"""End-to-end pipeline tests — LangGraph pipeline compiled with mocked LLM and ADO client."""

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


def _mock_ado(content: str | None = None, commit_sha: str = "deadbeef") -> MagicMock:
    """Mock ADO client — returns empty file content by default (no snippets)."""
    ado = MagicMock()
    ado.repository = "test-repo"
    ado.get_file_content = AsyncMock(return_value=content)
    ado.get_latest_commit_sha = AsyncMock(return_value=commit_sha)
    return ado


def _mock_search() -> MagicMock:
    """Mock AI Search client — returns empty results by default."""
    search = MagicMock()
    search.search = AsyncMock(return_value=[])
    return search


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
        pipeline = build_pipeline(
            llm=_mock_llm(), ado_client=_mock_ado(), search_client=_mock_search()
        )
        result: IncidentState = await pipeline.ainvoke(_make_initial_state())

        assert result.get("priority") is not None
        assert isinstance(result.get("triage_labels"), list)
        assert result.get("root_cause_summary") is not None

    @pytest.mark.asyncio
    async def test_triage_rule_path_skips_triage_llm(self) -> None:
        """When a triage rule matches, triage skips LLM; root_cause still calls it once."""
        llm = _mock_llm()
        pipeline = build_pipeline(llm=llm, ado_client=_mock_ado(), search_client=_mock_search())

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
        pipeline = build_pipeline(llm=llm, ado_client=_mock_ado(), search_client=_mock_search())

        await pipeline.ainvoke(
            _make_initial_state(exception_type="MyApp.CompletelyUnknownException")
        )

        assert llm.ainvoke.await_count == 2

    @pytest.mark.asyncio
    async def test_agent_trace_has_four_entries(self) -> None:
        pipeline = build_pipeline(
            llm=_mock_llm(), ado_client=_mock_ado(), search_client=_mock_search()
        )
        result: IncidentState = await pipeline.ainvoke(_make_initial_state())

        trace = result.get("agent_trace", [])
        assert len(trace) == 4
        assert trace[0]["agent_name"] == "triage"
        assert trace[1]["agent_name"] == "root_cause"
        assert trace[2]["agent_name"] == "code_context"
        assert trace[3]["agent_name"] == "rag"
        assert all("latency_ms" in e for e in trace)

    @pytest.mark.asyncio
    async def test_critical_exception_priority_in_final_state(self) -> None:
        pipeline = build_pipeline(
            llm=_mock_llm(), ado_client=_mock_ado(), search_client=_mock_search()
        )
        result: IncidentState = await pipeline.ainvoke(
            _make_initial_state(exception_type="System.OutOfMemoryException")
        )
        assert result["priority"] == "critical"
        assert "resource-exhaustion" in result["triage_labels"]

    @pytest.mark.asyncio
    async def test_errors_empty_on_clean_run(self) -> None:
        pipeline = build_pipeline(
            llm=_mock_llm(), ado_client=_mock_ado(), search_client=_mock_search()
        )
        result: IncidentState = await pipeline.ainvoke(_make_initial_state())
        assert result.get("errors", []) == []

    @pytest.mark.asyncio
    async def test_both_llm_agents_fail_gracefully(self) -> None:
        """Triage and root_cause LLM calls fail; code_context (no LLM) succeeds → 2 errors."""
        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=RuntimeError("Azure OpenAI unavailable"))
        pipeline = build_pipeline(llm=llm, ado_client=_mock_ado(), search_client=_mock_search())

        result: IncidentState = await pipeline.ainvoke(
            _make_initial_state(exception_type="Unknown.Error")
        )

        assert result["priority"] == "medium"
        assert "unknown" in result["triage_labels"]
        assert len(result.get("errors", [])) == 2

    @pytest.mark.asyncio
    async def test_root_cause_json_in_final_state(self) -> None:
        pipeline = build_pipeline(
            llm=_mock_llm(), ado_client=_mock_ado(), search_client=_mock_search()
        )
        result: IncidentState = await pipeline.ainvoke(_make_initial_state())

        rc = result.get("root_cause_json")
        assert rc is not None
        assert "component" in rc
        assert "confidence" in rc

    @pytest.mark.asyncio
    async def test_code_snippets_key_in_final_state(self) -> None:
        """code_snippets is present in state even when no files are fetched."""
        pipeline = build_pipeline(
            llm=_mock_llm(), ado_client=_mock_ado(), search_client=_mock_search()
        )
        result: IncidentState = await pipeline.ainvoke(_make_initial_state())
        assert "code_snippets" in result
        assert isinstance(result.get("code_snippets"), list)

    @pytest.mark.asyncio
    async def test_rag_results_key_in_final_state(self) -> None:
        """rag_results is present in state even when search returns nothing."""
        pipeline = build_pipeline(
            llm=_mock_llm(), ado_client=_mock_ado(), search_client=_mock_search()
        )
        result: IncidentState = await pipeline.ainvoke(_make_initial_state())
        assert "rag_results" in result
        assert isinstance(result.get("rag_results"), list)
