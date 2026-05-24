"""Unit tests for the bug_creator agent node — ADO Boards client is mocked throughout."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.agent_runtime.bug_creator.agent import AGENT_NAME, make_bug_creator_node
from packages.domain.models.agent_state import IncidentState


def _mock_boards(
    bug_id: int = 42, bug_url: str = "https://dev.azure.com/org/proj/_workitems/edit/42"
) -> MagicMock:
    client = MagicMock()
    client.create_bug = AsyncMock(
        return_value={
            "id": bug_id,
            "_links": {"html": {"href": bug_url}},
        }
    )
    return client


def _make_state(**overrides: object) -> IncidentState:
    base: IncidentState = {
        "incident_id": "bug-test-001",
        "correlation_id": "corr-bug",
        "exception_type": "System.NullReferenceException",
        "exception_message": "Object reference not set to an instance of an object.",
        "stack_trace": "",
        "raw_payload": {},
        "agent_trace": [],
        "errors": [],
        "triage_labels": ["null-reference"],
        "priority": "high",
        "root_cause_summary": "Null reference in UserService.GetById when DB returns null.",
        "root_cause_json": {
            "component": "UserService.GetById",
            "likely_cause": "Unguarded null return from repository",
            "contributing_factors": ["Missing null check"],
            "confidence": 0.8,
        },
        "recommendations": [
            {
                "rank": 1,
                "title": "Add null guard",
                "description": "Return 404 when user is missing.",
                "affected_files": ["svc.cs"],
                "suggested_change": "Add null check.",
                "confidence": 0.88,
                "source_refs": [],
            }
        ],
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


class TestBugCreatorNodeHappyPath:
    @pytest.mark.asyncio
    async def test_boards_client_is_called(self) -> None:
        client = _mock_boards()
        node = make_bug_creator_node(boards_client=client)
        await node(_make_state())
        client.create_bug.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_bug_id_returned(self) -> None:
        node = make_bug_creator_node(boards_client=_mock_boards(bug_id=99))
        result = await node(_make_state())
        assert result["ado_bug_id"] == 99

    @pytest.mark.asyncio
    async def test_bug_url_returned(self) -> None:
        url = "https://dev.azure.com/myorg/myproj/_workitems/edit/42"
        node = make_bug_creator_node(boards_client=_mock_boards(bug_url=url))
        result = await node(_make_state())
        assert result["ado_bug_url"] == url

    @pytest.mark.asyncio
    async def test_no_errors_on_clean_run(self) -> None:
        node = make_bug_creator_node(boards_client=_mock_boards())
        result = await node(_make_state())
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_trace_entry_appended(self) -> None:
        node = make_bug_creator_node(boards_client=_mock_boards())
        result = await node(_make_state())
        assert len(result["agent_trace"]) == 1
        entry = result["agent_trace"][0]
        assert entry["agent_name"] == AGENT_NAME
        assert entry["prompt_version"] is None
        assert entry["error"] is None

    @pytest.mark.asyncio
    async def test_title_includes_priority_and_exception_type(self) -> None:
        client = _mock_boards()
        node = make_bug_creator_node(boards_client=client)
        await node(_make_state(priority="critical"))
        call_kwargs = client.create_bug.call_args.kwargs
        title: str = call_kwargs.get("title") or client.create_bug.call_args[1].get("title") or ""
        assert "CRITICAL" in title
        assert "NullReferenceException" in title

    @pytest.mark.asyncio
    async def test_priority_passed_to_client(self) -> None:
        client = _mock_boards()
        node = make_bug_creator_node(boards_client=client)
        await node(_make_state(priority="high"))
        call_kwargs = client.create_bug.call_args.kwargs
        priority = call_kwargs.get("priority") or client.create_bug.call_args[1].get("priority")
        assert priority == "high"

    @pytest.mark.asyncio
    async def test_tags_include_triage_labels(self) -> None:
        client = _mock_boards()
        node = make_bug_creator_node(boards_client=client)
        await node(_make_state(triage_labels=["null-reference", "critical-path"]))
        call_kwargs = client.create_bug.call_args.kwargs
        tags: str = call_kwargs.get("tags") or client.create_bug.call_args[1].get("tags") or ""
        assert "null-reference" in tags
        assert "critical-path" in tags

    @pytest.mark.asyncio
    async def test_description_contains_root_cause(self) -> None:
        client = _mock_boards()
        node = make_bug_creator_node(boards_client=client)
        await node(_make_state())
        call_kwargs = client.create_bug.call_args.kwargs
        desc: str = call_kwargs.get("description") or ""
        assert "UserService.GetById" in desc

    @pytest.mark.asyncio
    async def test_existing_trace_preserved(self) -> None:
        prior: list[Any] = [{"agent_name": "fix_planner", "output_summary": "recommendations=1"}]
        state = _make_state(agent_trace=prior)
        node = make_bug_creator_node(boards_client=_mock_boards())
        result = await node(state)
        assert len(result["agent_trace"]) == 2
        assert result["agent_trace"][0]["agent_name"] == "fix_planner"
        assert result["agent_trace"][1]["agent_name"] == AGENT_NAME


class TestBugCreatorNodeSkipBehaviour:
    @pytest.mark.asyncio
    async def test_no_client_returns_none_ids(self) -> None:
        node = make_bug_creator_node(boards_client=None, settings=object())
        result = await node(_make_state())
        assert result["ado_bug_id"] is None
        assert result["ado_bug_url"] is None

    @pytest.mark.asyncio
    async def test_no_client_appends_no_error(self) -> None:
        node = make_bug_creator_node(boards_client=None, settings=object())
        result = await node(_make_state())
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_no_client_trace_entry_still_added(self) -> None:
        node = make_bug_creator_node(boards_client=None, settings=object())
        result = await node(_make_state())
        assert len(result["agent_trace"]) == 1
        assert result["agent_trace"][0]["agent_name"] == AGENT_NAME


class TestBugCreatorNodeFailurePath:
    @pytest.mark.asyncio
    async def test_api_failure_appends_error(self) -> None:
        client = MagicMock()
        client.create_bug = AsyncMock(side_effect=RuntimeError("ADO unavailable"))
        node = make_bug_creator_node(boards_client=client)
        result = await node(_make_state())
        assert len(result["errors"]) == 1
        assert "ADO unavailable" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_api_failure_returns_none_ids(self) -> None:
        client = MagicMock()
        client.create_bug = AsyncMock(side_effect=RuntimeError("network error"))
        node = make_bug_creator_node(boards_client=client)
        result = await node(_make_state())
        assert result["ado_bug_id"] is None
        assert result["ado_bug_url"] is None

    @pytest.mark.asyncio
    async def test_api_failure_trace_records_error(self) -> None:
        client = MagicMock()
        client.create_bug = AsyncMock(side_effect=RuntimeError("timeout"))
        node = make_bug_creator_node(boards_client=client)
        result = await node(_make_state())
        assert result["agent_trace"][0]["error"] is not None

    @pytest.mark.asyncio
    async def test_existing_errors_preserved_on_failure(self) -> None:
        client = MagicMock()
        client.create_bug = AsyncMock(side_effect=RuntimeError("fail"))
        state = _make_state(errors=["prior-error"])
        node = make_bug_creator_node(boards_client=client)
        result = await node(state)
        assert "prior-error" in result["errors"]
        assert len(result["errors"]) == 2
