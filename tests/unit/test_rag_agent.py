"""Unit tests for the RAG retrieval agent node — search client is mocked throughout."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.agent_runtime.rag.agent import (
    _SCORE_THRESHOLD,
    AGENT_NAME,
    make_rag_node,
)
from packages.domain.models.agent_state import IncidentState


def _make_raw_result(
    score: float = 0.85,
    title: str = "Null Reference Runbook",
    content: str = "Check for null guards before dereferencing objects.",
    source_type: str = "runbook",
    url: str | None = "https://wiki/null-reference",
) -> dict[str, Any]:
    return {
        "@search.score": score,
        "title": title,
        "content": content,
        "source_type": source_type,
        "url": url,
    }


def _mock_search(results: list[dict[str, Any]] | None = None) -> MagicMock:
    client = MagicMock()
    client.search = AsyncMock(return_value=results if results is not None else [])
    return client


def _make_state(**overrides: object) -> IncidentState:
    base: IncidentState = {
        "incident_id": "rag-test-001",
        "correlation_id": "corr-rag",
        "exception_type": "System.NullReferenceException",
        "exception_message": "Object reference not set.",
        "stack_trace": "",
        "raw_payload": {},
        "agent_trace": [],
        "errors": [],
        "triage_labels": ["null-reference"],
        "root_cause_summary": "Null reference in UserService.GetById when DB returns null.",
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


class TestRagNodeHappyPath:
    @pytest.mark.asyncio
    async def test_search_client_is_called(self) -> None:
        client = _mock_search()
        node = make_rag_node(search_client=client)
        await node(_make_state())
        client.search.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_query_includes_root_cause_and_exception_type(self) -> None:
        client = _mock_search()
        node = make_rag_node(search_client=client)
        await node(_make_state())
        call_args = client.search.call_args
        query: str = call_args.kwargs.get("query") or call_args[1].get("query") or call_args[0][0]
        assert "NullReferenceException" in query or "null-reference" in query

    @pytest.mark.asyncio
    async def test_high_score_result_included(self) -> None:
        client = _mock_search([_make_raw_result(score=0.9)])
        node = make_rag_node(search_client=client)
        result = await node(_make_state())
        assert len(result["rag_results"]) == 1
        assert result["rag_results"][0]["title"] == "Null Reference Runbook"

    @pytest.mark.asyncio
    async def test_low_score_result_filtered(self) -> None:
        client = _mock_search([_make_raw_result(score=_SCORE_THRESHOLD)])
        node = make_rag_node(search_client=client)
        result = await node(_make_state())
        assert result["rag_results"] == []

    @pytest.mark.asyncio
    async def test_results_sorted_by_source_priority(self) -> None:
        raw = [
            _make_raw_result(score=0.9, source_type="documentation", title="Doc"),
            _make_raw_result(score=0.9, source_type="runbook", title="Runbook"),
            _make_raw_result(score=0.9, source_type="prior_fix", title="Fix"),
        ]
        client = _mock_search(raw)
        node = make_rag_node(search_client=client)
        result = await node(_make_state())
        sources = [r["source"] for r in result["rag_results"]]
        assert sources[0] == "runbook"
        assert sources[1] == "prior_fix"
        assert sources[2] == "documentation"

    @pytest.mark.asyncio
    async def test_results_limited_to_five(self) -> None:
        raw = [_make_raw_result(score=0.9, title=f"Result {i}") for i in range(10)]
        client = _mock_search(raw)
        node = make_rag_node(search_client=client)
        result = await node(_make_state())
        assert len(result["rag_results"]) <= 5

    @pytest.mark.asyncio
    async def test_no_errors_on_clean_run(self) -> None:
        client = _mock_search()
        node = make_rag_node(search_client=client)
        result = await node(_make_state())
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_trace_entry_appended(self) -> None:
        client = _mock_search()
        node = make_rag_node(search_client=client)
        result = await node(_make_state())
        assert len(result["agent_trace"]) == 1
        entry = result["agent_trace"][0]
        assert entry["agent_name"] == AGENT_NAME
        assert entry["prompt_version"] is None
        assert entry["error"] is None

    @pytest.mark.asyncio
    async def test_empty_results_returns_empty_list(self) -> None:
        client = _mock_search([])
        node = make_rag_node(search_client=client)
        result = await node(_make_state())
        assert result["rag_results"] == []

    @pytest.mark.asyncio
    async def test_excerpt_truncated_to_500_chars(self) -> None:
        long_content = "x" * 1000
        raw = [_make_raw_result(score=0.9, content=long_content)]
        client = _mock_search(raw)
        node = make_rag_node(search_client=client)
        result = await node(_make_state())
        assert len(result["rag_results"][0]["excerpt"]) <= 500

    @pytest.mark.asyncio
    async def test_result_url_preserved(self) -> None:
        raw = [_make_raw_result(score=0.9, url="https://wiki/fix")]
        client = _mock_search(raw)
        node = make_rag_node(search_client=client)
        result = await node(_make_state())
        assert result["rag_results"][0]["url"] == "https://wiki/fix"

    @pytest.mark.asyncio
    async def test_result_without_url_is_none(self) -> None:
        raw = [_make_raw_result(score=0.9, url=None)]
        client = _mock_search(raw)
        node = make_rag_node(search_client=client)
        result = await node(_make_state())
        assert result["rag_results"][0]["url"] is None

    @pytest.mark.asyncio
    async def test_empty_root_cause_summary_still_searches(self) -> None:
        client = _mock_search()
        node = make_rag_node(search_client=client)
        await node(_make_state(root_cause_summary=""))
        client.search.assert_awaited_once()


class TestRagNodeFailurePath:
    @pytest.mark.asyncio
    async def test_search_failure_appends_error(self) -> None:
        client = MagicMock()
        client.search = AsyncMock(side_effect=RuntimeError("AI Search unavailable"))
        node = make_rag_node(search_client=client)
        result = await node(_make_state())
        assert len(result["errors"]) == 1
        assert "AI Search unavailable" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_search_failure_trace_records_error(self) -> None:
        client = MagicMock()
        client.search = AsyncMock(side_effect=RuntimeError("timeout"))
        node = make_rag_node(search_client=client)
        result = await node(_make_state())
        assert result["agent_trace"][0]["error"] is not None

    @pytest.mark.asyncio
    async def test_search_failure_returns_empty_rag_results(self) -> None:
        client = MagicMock()
        client.search = AsyncMock(side_effect=RuntimeError("network error"))
        node = make_rag_node(search_client=client)
        result = await node(_make_state())
        assert result["rag_results"] == []


class TestRagNodeStateIntegration:
    @pytest.mark.asyncio
    async def test_existing_trace_preserved(self) -> None:
        existing = [{"agent_name": "code_context", "output_summary": "snippets=0"}]
        state = _make_state(agent_trace=existing)
        node = make_rag_node(search_client=_mock_search())
        result = await node(state)
        assert len(result["agent_trace"]) == 2
        assert result["agent_trace"][0]["agent_name"] == "code_context"
        assert result["agent_trace"][1]["agent_name"] == AGENT_NAME

    @pytest.mark.asyncio
    async def test_existing_errors_preserved_on_new_error(self) -> None:
        client = MagicMock()
        client.search = AsyncMock(side_effect=RuntimeError("fail"))
        state = _make_state(errors=["prior-error"])
        node = make_rag_node(search_client=client)
        result = await node(state)
        assert "prior-error" in result["errors"]
        assert len(result["errors"]) == 2
