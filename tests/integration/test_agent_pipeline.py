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

_FP_JSON = json.dumps(
    {
        "recommendations": [
            {
                "rank": 1,
                "title": "Add null guard",
                "description": "Return 404 when user is missing.",
                "affected_files": ["svc.cs"],
                "suggested_change": "Add null check before mapping.",
                "confidence": 0.85,
                "source_refs": ["runbook:null"],
            }
        ]
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
    """Mock ADO Repos client — returns empty file content by default (no snippets)."""
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


def _mock_boards(bug_id: int = 1001) -> MagicMock:
    """Mock ADO Boards client — returns a created bug by default."""
    boards = MagicMock()
    boards.create_bug = AsyncMock(
        return_value={
            "id": bug_id,
            "_links": {"html": {"href": f"https://dev.azure.com/org/proj/_workitems/edit/{bug_id}"}},
        }
    )
    return boards


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
    async def test_pipeline_runs_all_nodes(self) -> None:
        """Full pipeline produces priority, root_cause_summary, recommendations, and bug ID."""
        pipeline = build_pipeline(
            llm=_mock_llm_sequence(_RC_JSON, _FP_JSON),
            ado_client=_mock_ado(),
            search_client=_mock_search(),
            boards_client=_mock_boards(),
        )
        result: IncidentState = await pipeline.ainvoke(_make_initial_state())

        assert result.get("priority") is not None
        assert isinstance(result.get("triage_labels"), list)
        assert result.get("root_cause_summary") is not None
        assert isinstance(result.get("recommendations"), list)

    @pytest.mark.asyncio
    async def test_triage_rule_path_skips_triage_llm(self) -> None:
        """When a triage rule matches, triage skips LLM; root_cause and fix_planner call it."""
        llm = _mock_llm_sequence(_RC_JSON, _FP_JSON)
        pipeline = build_pipeline(
            llm=llm,
            ado_client=_mock_ado(),
            search_client=_mock_search(),
            boards_client=_mock_boards(),
        )

        result: IncidentState = await pipeline.ainvoke(
            _make_initial_state(exception_type="System.NullReferenceException")
        )

        assert llm.ainvoke.await_count == 2  # root_cause + fix_planner
        assert result["priority"] == "high"
        assert "null-reference" in result["triage_labels"]

    @pytest.mark.asyncio
    async def test_llm_path_called_for_unknown_exception(self) -> None:
        """Triage, root_cause, and fix_planner all call LLM when no rule matches."""
        llm = _mock_llm_sequence(_TRIAGE_JSON, _RC_JSON, _FP_JSON)
        pipeline = build_pipeline(
            llm=llm,
            ado_client=_mock_ado(),
            search_client=_mock_search(),
            boards_client=_mock_boards(),
        )

        await pipeline.ainvoke(
            _make_initial_state(exception_type="MyApp.CompletelyUnknownException")
        )

        assert llm.ainvoke.await_count == 3

    @pytest.mark.asyncio
    async def test_agent_trace_has_six_entries(self) -> None:
        pipeline = build_pipeline(
            llm=_mock_llm_sequence(_RC_JSON, _FP_JSON),
            ado_client=_mock_ado(),
            search_client=_mock_search(),
            boards_client=_mock_boards(),
        )
        result: IncidentState = await pipeline.ainvoke(_make_initial_state())

        trace = result.get("agent_trace", [])
        assert len(trace) == 6
        assert trace[0]["agent_name"] == "triage"
        assert trace[1]["agent_name"] == "root_cause"
        assert trace[2]["agent_name"] == "code_context"
        assert trace[3]["agent_name"] == "rag"
        assert trace[4]["agent_name"] == "fix_planner"
        assert trace[5]["agent_name"] == "bug_creator"
        assert all("latency_ms" in e for e in trace)

    @pytest.mark.asyncio
    async def test_critical_exception_priority_in_final_state(self) -> None:
        pipeline = build_pipeline(
            llm=_mock_llm_sequence(_RC_JSON, _FP_JSON),
            ado_client=_mock_ado(),
            search_client=_mock_search(),
            boards_client=_mock_boards(),
        )
        result: IncidentState = await pipeline.ainvoke(
            _make_initial_state(exception_type="System.OutOfMemoryException")
        )
        assert result["priority"] == "critical"
        assert "resource-exhaustion" in result["triage_labels"]

    @pytest.mark.asyncio
    async def test_errors_empty_on_clean_run(self) -> None:
        pipeline = build_pipeline(
            llm=_mock_llm_sequence(_RC_JSON, _FP_JSON),
            ado_client=_mock_ado(),
            search_client=_mock_search(),
            boards_client=_mock_boards(),
        )
        result: IncidentState = await pipeline.ainvoke(_make_initial_state())
        assert result.get("errors", []) == []

    @pytest.mark.asyncio
    async def test_all_llm_agents_fail_gracefully(self) -> None:
        """Triage, root_cause, fix_planner fail; code_context, rag, bug_creator succeed → 3 errors."""
        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=RuntimeError("Azure OpenAI unavailable"))
        pipeline = build_pipeline(
            llm=llm,
            ado_client=_mock_ado(),
            search_client=_mock_search(),
            boards_client=_mock_boards(),
        )

        result: IncidentState = await pipeline.ainvoke(
            _make_initial_state(exception_type="Unknown.Error")
        )

        assert result["priority"] == "medium"
        assert "unknown" in result["triage_labels"]
        assert len(result.get("errors", [])) == 3

    @pytest.mark.asyncio
    async def test_root_cause_json_in_final_state(self) -> None:
        pipeline = build_pipeline(
            llm=_mock_llm_sequence(_RC_JSON, _FP_JSON),
            ado_client=_mock_ado(),
            search_client=_mock_search(),
            boards_client=_mock_boards(),
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
            llm=_mock_llm_sequence(_RC_JSON, _FP_JSON),
            ado_client=_mock_ado(),
            search_client=_mock_search(),
            boards_client=_mock_boards(),
        )
        result: IncidentState = await pipeline.ainvoke(_make_initial_state())
        assert "code_snippets" in result
        assert isinstance(result.get("code_snippets"), list)

    @pytest.mark.asyncio
    async def test_rag_results_key_in_final_state(self) -> None:
        """rag_results is present in state even when search returns nothing."""
        pipeline = build_pipeline(
            llm=_mock_llm_sequence(_RC_JSON, _FP_JSON),
            ado_client=_mock_ado(),
            search_client=_mock_search(),
            boards_client=_mock_boards(),
        )
        result: IncidentState = await pipeline.ainvoke(_make_initial_state())
        assert "rag_results" in result
        assert isinstance(result.get("rag_results"), list)

    @pytest.mark.asyncio
    async def test_recommendations_key_in_final_state(self) -> None:
        """recommendations is present in state after fix_planner runs."""
        pipeline = build_pipeline(
            llm=_mock_llm_sequence(_RC_JSON, _FP_JSON),
            ado_client=_mock_ado(),
            search_client=_mock_search(),
            boards_client=_mock_boards(),
        )
        result: IncidentState = await pipeline.ainvoke(_make_initial_state())
        assert "recommendations" in result
        assert isinstance(result.get("recommendations"), list)

    @pytest.mark.asyncio
    async def test_ado_bug_id_in_final_state(self) -> None:
        """ado_bug_id is set when boards_client creates a work item."""
        pipeline = build_pipeline(
            llm=_mock_llm_sequence(_RC_JSON, _FP_JSON),
            ado_client=_mock_ado(),
            search_client=_mock_search(),
            boards_client=_mock_boards(bug_id=999),
        )
        result: IncidentState = await pipeline.ainvoke(_make_initial_state())
        assert result.get("ado_bug_id") == 999
        assert result.get("ado_bug_url") is not None

    @pytest.mark.asyncio
    async def test_no_boards_client_skips_bug_creation(self) -> None:
        """With no boards_client and unconfigured settings, bug_creator skips gracefully."""
        pipeline = build_pipeline(
            llm=_mock_llm_sequence(_RC_JSON, _FP_JSON),
            ado_client=_mock_ado(),
            search_client=_mock_search(),
            boards_client=None,
            settings=object(),
        )
        result: IncidentState = await pipeline.ainvoke(_make_initial_state())
        assert result.get("ado_bug_id") is None
        assert result.get("errors", []) == []
