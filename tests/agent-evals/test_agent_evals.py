"""Agent eval harness — runs the full pipeline against sample incident fixtures.

Each fixture in tests/agent-evals/fixtures/*.json defines an input state and
``expected`` assertions.  The LLM, ADO Repos, AI Search, and ADO Boards clients
are mocked so the harness runs in CI without any Azure credentials.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage

from packages.agent_runtime.pipeline import build_pipeline
from packages.domain.models.agent_state import IncidentState

_FIXTURES_DIR = Path(__file__).parent / "fixtures"

_RC_JSON = json.dumps(
    {
        "root_cause_summary": "Unguarded null or resource exhaustion detected in the service layer.",
        "root_cause_json": {
            "component": "ServiceLayer",
            "likely_cause": "Missing defensive check before operation.",
            "contributing_factors": ["No null guard", "No retry logic"],
            "confidence": 0.78,
        },
        "evidence": ["Top user-code frame points to service layer"],
    }
)

_TRIAGE_JSON = json.dumps(
    {
        "priority": "high",
        "triage_labels": ["gateway-error", "transient"],
        "group_id": None,
        "rationale": "Payment gateway 503 suggests transient upstream failure.",
        "confidence": 0.72,
    }
)

_FP_JSON = json.dumps(
    {
        "recommendations": [
            {
                "rank": 1,
                "title": "Add retry with exponential back-off",
                "description": "Wrap the gateway call in a Polly retry policy.",
                "affected_files": ["src/integrations/PaymentGatewayClient.cs"],
                "suggested_change": "Apply RetryPolicy<HttpResponseMessage> for 503 responses.",
                "confidence": 0.84,
                "source_refs": ["runbook:gateway-retry"],
            }
        ]
    }
)


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((_FIXTURES_DIR / name).read_text(encoding="utf-8"))


def _make_state(fixture: dict[str, Any]) -> IncidentState:
    keys = {
        "incident_id", "correlation_id", "exception_type", "exception_message",
        "stack_trace", "raw_payload", "agent_trace", "errors", "triage_labels",
    }
    return {k: fixture[k] for k in keys if k in fixture}  # type: ignore[return-value]


def _mock_ado() -> MagicMock:
    ado = MagicMock()
    ado.repository = "eval-repo"
    ado.get_file_content = AsyncMock(return_value=None)
    ado.get_latest_commit_sha = AsyncMock(return_value="abc123")
    return ado


def _mock_search() -> MagicMock:
    search = MagicMock()
    search.search = AsyncMock(return_value=[])
    return search


def _mock_boards(bug_id: int = 9001) -> MagicMock:
    boards = MagicMock()
    boards.create_bug = AsyncMock(
        return_value={"id": bug_id, "_links": {"html": {"href": f"https://dev.azure.com/{bug_id}"}}}
    )
    return boards


def _mock_llm_rule_path() -> MagicMock:
    """For rule-matched incidents: root_cause + fix_planner each get one call."""
    llm = MagicMock()
    llm.ainvoke = AsyncMock(side_effect=[AIMessage(content=_RC_JSON), AIMessage(content=_FP_JSON)])
    return llm


def _mock_llm_llm_path() -> MagicMock:
    """For unknown exceptions: triage + root_cause + fix_planner each get one call."""
    llm = MagicMock()
    llm.ainvoke = AsyncMock(
        side_effect=[
            AIMessage(content=_TRIAGE_JSON),
            AIMessage(content=_RC_JSON),
            AIMessage(content=_FP_JSON),
        ]
    )
    return llm


class TestNullReferenceFixture:
    @pytest.mark.asyncio
    async def test_null_reference_priority_and_labels(self) -> None:
        fixture = _load_fixture("null_reference.json")
        expected = fixture["expected"]
        pipeline = build_pipeline(
            llm=_mock_llm_rule_path(),
            ado_client=_mock_ado(),
            search_client=_mock_search(),
            boards_client=_mock_boards(),
        )
        result: IncidentState = await pipeline.ainvoke(_make_state(fixture))

        assert result["priority"] == expected["priority"]
        for label in expected["triage_labels_contains"]:
            assert label in result["triage_labels"]

    @pytest.mark.asyncio
    async def test_null_reference_full_trace(self) -> None:
        fixture = _load_fixture("null_reference.json")
        expected = fixture["expected"]
        pipeline = build_pipeline(
            llm=_mock_llm_rule_path(),
            ado_client=_mock_ado(),
            search_client=_mock_search(),
            boards_client=_mock_boards(),
        )
        result: IncidentState = await pipeline.ainvoke(_make_state(fixture))

        agent_names = [e["agent_name"] for e in result.get("agent_trace", [])]
        assert agent_names == expected["trace_agent_names"]

    @pytest.mark.asyncio
    async def test_null_reference_no_errors(self) -> None:
        fixture = _load_fixture("null_reference.json")
        pipeline = build_pipeline(
            llm=_mock_llm_rule_path(),
            ado_client=_mock_ado(),
            search_client=_mock_search(),
            boards_client=_mock_boards(),
        )
        result: IncidentState = await pipeline.ainvoke(_make_state(fixture))
        assert result.get("errors", []) == []

    @pytest.mark.asyncio
    async def test_null_reference_triage_uses_rule_not_llm(self) -> None:
        fixture = _load_fixture("null_reference.json")
        llm = _mock_llm_rule_path()
        pipeline = build_pipeline(
            llm=llm,
            ado_client=_mock_ado(),
            search_client=_mock_search(),
            boards_client=_mock_boards(),
        )
        await pipeline.ainvoke(_make_state(fixture))
        assert llm.ainvoke.await_count == 2  # root_cause + fix_planner; triage used rule


class TestOutOfMemoryFixture:
    @pytest.mark.asyncio
    async def test_oom_priority_critical(self) -> None:
        fixture = _load_fixture("out_of_memory.json")
        expected = fixture["expected"]
        pipeline = build_pipeline(
            llm=_mock_llm_rule_path(),
            ado_client=_mock_ado(),
            search_client=_mock_search(),
            boards_client=_mock_boards(),
        )
        result: IncidentState = await pipeline.ainvoke(_make_state(fixture))
        assert result["priority"] == expected["priority"]
        for label in expected["triage_labels_contains"]:
            assert label in result["triage_labels"]

    @pytest.mark.asyncio
    async def test_oom_has_root_cause_and_recommendations(self) -> None:
        fixture = _load_fixture("out_of_memory.json")
        pipeline = build_pipeline(
            llm=_mock_llm_rule_path(),
            ado_client=_mock_ado(),
            search_client=_mock_search(),
            boards_client=_mock_boards(),
        )
        result: IncidentState = await pipeline.ainvoke(_make_state(fixture))
        assert result.get("root_cause_summary")
        assert isinstance(result.get("recommendations"), list)
        assert len(result["recommendations"]) >= 1

    @pytest.mark.asyncio
    async def test_oom_bug_created(self) -> None:
        fixture = _load_fixture("out_of_memory.json")
        pipeline = build_pipeline(
            llm=_mock_llm_rule_path(),
            ado_client=_mock_ado(),
            search_client=_mock_search(),
            boards_client=_mock_boards(bug_id=9999),
        )
        result: IncidentState = await pipeline.ainvoke(_make_state(fixture))
        assert result.get("ado_bug_id") == 9999


class TestUnknownExceptionFixture:
    @pytest.mark.asyncio
    async def test_unknown_calls_llm_for_triage(self) -> None:
        fixture = _load_fixture("unknown_exception.json")
        expected = fixture["expected"]
        llm = _mock_llm_llm_path()
        pipeline = build_pipeline(
            llm=llm,
            ado_client=_mock_ado(),
            search_client=_mock_search(),
            boards_client=_mock_boards(),
        )
        await pipeline.ainvoke(_make_state(fixture))
        assert llm.ainvoke.await_count == expected["llm_call_count"]

    @pytest.mark.asyncio
    async def test_unknown_has_all_trace_agents(self) -> None:
        fixture = _load_fixture("unknown_exception.json")
        expected = fixture["expected"]
        pipeline = build_pipeline(
            llm=_mock_llm_llm_path(),
            ado_client=_mock_ado(),
            search_client=_mock_search(),
            boards_client=_mock_boards(),
        )
        result: IncidentState = await pipeline.ainvoke(_make_state(fixture))
        agent_names = [e["agent_name"] for e in result.get("agent_trace", [])]
        assert agent_names == expected["trace_agent_names"]

    @pytest.mark.asyncio
    async def test_unknown_has_root_cause_and_recommendations(self) -> None:
        fixture = _load_fixture("unknown_exception.json")
        pipeline = build_pipeline(
            llm=_mock_llm_llm_path(),
            ado_client=_mock_ado(),
            search_client=_mock_search(),
            boards_client=_mock_boards(),
        )
        result: IncidentState = await pipeline.ainvoke(_make_state(fixture))
        assert result.get("root_cause_summary")
        assert len(result.get("recommendations", [])) >= 1


class TestPromptRegistry:
    def test_registry_loads_triage_prompt(self) -> None:
        from packages.agent_runtime.prompt_registry import PromptRegistry
        registry = PromptRegistry()
        content = registry.load("triage", "1")
        assert "## Goal" in content
        assert len(content) > 100

    def test_registry_loads_root_cause_prompt(self) -> None:
        from packages.agent_runtime.prompt_registry import PromptRegistry
        registry = PromptRegistry()
        content = registry.load("root_cause", "1")
        assert "## Goal" in content

    def test_registry_loads_fix_planner_prompt(self) -> None:
        from packages.agent_runtime.prompt_registry import PromptRegistry
        registry = PromptRegistry()
        content = registry.load("fix_planner", "1")
        assert "## Goal" in content

    def test_registry_caches_on_second_load(self) -> None:
        from packages.agent_runtime.prompt_registry import PromptRegistry
        registry = PromptRegistry()
        first = registry.load("triage", "1")
        second = registry.load("triage", "1")
        assert first is second  # same object from cache

    def test_registry_available_versions(self) -> None:
        from packages.agent_runtime.prompt_registry import PromptRegistry
        registry = PromptRegistry()
        versions = registry.available_versions("triage")
        assert "1" in versions

    def test_registry_clear_cache(self) -> None:
        from packages.agent_runtime.prompt_registry import PromptRegistry
        registry = PromptRegistry()
        registry.load("triage", "1")
        registry.clear_cache()
        assert len(registry._cache) == 0  # noqa: SLF001
