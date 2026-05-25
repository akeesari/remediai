"""Unit tests for the Code Context agent node — ADO client is mocked throughout."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.agent_runtime.code_context.agent import AGENT_NAME, make_code_context_node
from packages.domain.models.agent_state import IncidentState

_FILE_CONTENT = "\n".join(f"line {i}" for i in range(1, 101))  # 100-line file

_STACK_WITH_FILE = (
    "   at UserService.GetById(Int32 id) in src/UserService.cs:line 42\n"
    "   at System.Linq.Enumerable.First(IEnumerable src)"
)
_STACK_NO_FILE = "   at UserService.GetById(Int32 id)"  # no file path
_STACK_FRAMEWORK_ONLY = "   at System.Linq.Enumerable.First(IEnumerable src)"


def _mock_ado(
    content: str | None = _FILE_CONTENT,
    commit_sha: str = "deadbeef",
    repo: str = "test-repo",
) -> MagicMock:
    ado = MagicMock()
    ado.repository = repo
    ado.get_file_content = AsyncMock(return_value=content)
    ado.get_latest_commit_sha = AsyncMock(return_value=commit_sha)
    return ado


def _make_state(**overrides: object) -> IncidentState:
    base: IncidentState = {
        "incident_id": "cc-test-001",
        "correlation_id": "corr-cc",
        "exception_type": "System.NullReferenceException",
        "exception_message": "Object reference not set.",
        "stack_trace": _STACK_WITH_FILE,
        "raw_payload": {},
        "agent_trace": [],
        "errors": [],
        "triage_labels": ["null-reference"],
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


class TestCodeContextNodeHappyPath:
    @pytest.mark.asyncio
    async def test_fetches_snippet_for_user_code_frame(self) -> None:
        ado = _mock_ado()
        node = make_code_context_node(ado_client=ado)
        result = await node(_make_state())
        ado.get_file_content.assert_awaited_once_with("src/UserService.cs")
        assert len(result["code_snippets"]) == 1

    @pytest.mark.asyncio
    async def test_snippet_metadata_correct(self) -> None:
        ado = _mock_ado(commit_sha="abc123", repo="my-repo")
        node = make_code_context_node(ado_client=ado)
        result = await node(_make_state())
        snippet = result["code_snippets"][0]
        assert snippet["file_path"] == "src/UserService.cs"
        assert snippet["repo"] == "my-repo"
        assert snippet["commit_sha"] == "abc123"

    @pytest.mark.asyncio
    async def test_line_window_extracted_correctly(self) -> None:
        ado = _mock_ado()
        node = make_code_context_node(ado_client=ado)
        result = await node(_make_state())
        snippet = result["code_snippets"][0]
        # line 42, context 20: start=22, end=62
        assert snippet["start_line"] == 22
        assert snippet["end_line"] == 62

    @pytest.mark.asyncio
    async def test_skips_framework_frames(self) -> None:
        ado = _mock_ado()
        node = make_code_context_node(ado_client=ado)
        await node(_make_state())
        # System.Linq.Enumerable is framework — only the user frame is fetched
        ado.get_file_content.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_frames_without_file_path(self) -> None:
        ado = _mock_ado()
        node = make_code_context_node(ado_client=ado)
        result = await node(_make_state(stack_trace=_STACK_NO_FILE))
        assert result["code_snippets"] == []
        ado.get_file_content.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_stack_trace_returns_empty_snippets(self) -> None:
        ado = _mock_ado()
        node = make_code_context_node(ado_client=ado)
        result = await node(_make_state(stack_trace=""))
        assert result["code_snippets"] == []

    @pytest.mark.asyncio
    async def test_ado_returns_none_file_skipped(self) -> None:
        ado = _mock_ado(content=None)
        node = make_code_context_node(ado_client=ado)
        result = await node(_make_state())
        assert result["code_snippets"] == []

    @pytest.mark.asyncio
    async def test_only_framework_frames_returns_empty(self) -> None:
        ado = _mock_ado()
        node = make_code_context_node(ado_client=ado)
        result = await node(_make_state(stack_trace=_STACK_FRAMEWORK_ONLY))
        assert result["code_snippets"] == []
        ado.get_file_content.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_limits_to_five_snippets(self) -> None:
        lines = [f"   at UserService.Method{i}() in src/Svc.cs:line {i * 10}" for i in range(1, 9)]
        ado = _mock_ado()
        node = make_code_context_node(ado_client=ado)
        result = await node(_make_state(stack_trace="\n".join(lines)))
        assert len(result["code_snippets"]) <= 5

    @pytest.mark.asyncio
    async def test_no_errors_on_clean_run(self) -> None:
        ado = _mock_ado()
        node = make_code_context_node(ado_client=ado)
        result = await node(_make_state())
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_trace_entry_appended(self) -> None:
        ado = _mock_ado()
        node = make_code_context_node(ado_client=ado)
        result = await node(_make_state())
        assert len(result["agent_trace"]) == 1
        entry = result["agent_trace"][0]
        assert entry["agent_name"] == AGENT_NAME
        assert entry["prompt_version"] is None  # no LLM
        assert entry["error"] is None

    @pytest.mark.asyncio
    async def test_line_near_top_of_file_clamped(self) -> None:
        ado = _mock_ado()
        node = make_code_context_node(ado_client=ado)
        # line 3, context 20: start should be clamped to 1
        state = _make_state(stack_trace="   at MyService.Init() in src/MyService.cs:line 3")
        result = await node(state)
        assert result["code_snippets"][0]["start_line"] == 1

    @pytest.mark.asyncio
    async def test_missing_scm_configuration_skips_without_error(self) -> None:
        node = make_code_context_node(settings=SimpleNamespace(scm_provider_id="none"))

        result = await node(_make_state())

        assert result["code_snippets"] == []
        assert result["errors"] == []
        assert len(result["agent_trace"]) == 1
        assert result["agent_trace"][0]["error"] is None


class TestCodeContextNodeFailurePath:
    @pytest.mark.asyncio
    async def test_ado_exception_appends_error(self) -> None:
        ado = MagicMock()
        ado.repository = "repo"
        ado.get_latest_commit_sha = AsyncMock(return_value="abc")
        ado.get_file_content = AsyncMock(side_effect=RuntimeError("ADO down"))
        node = make_code_context_node(ado_client=ado)
        result = await node(_make_state())
        assert len(result["errors"]) == 1
        assert "ADO down" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_ado_exception_trace_records_error(self) -> None:
        ado = MagicMock()
        ado.repository = "repo"
        ado.get_latest_commit_sha = AsyncMock(return_value="abc")
        ado.get_file_content = AsyncMock(side_effect=RuntimeError("timeout"))
        node = make_code_context_node(ado_client=ado)
        result = await node(_make_state())
        assert result["agent_trace"][0]["error"] is not None


class TestCodeContextNodeStateIntegration:
    @pytest.mark.asyncio
    async def test_existing_trace_preserved(self) -> None:
        existing = [{"agent_name": "root_cause", "output_summary": "x"}]
        state = _make_state(agent_trace=existing)
        ado = _mock_ado()
        node = make_code_context_node(ado_client=ado)
        result = await node(state)
        assert len(result["agent_trace"]) == 2
        assert result["agent_trace"][0]["agent_name"] == "root_cause"
        assert result["agent_trace"][1]["agent_name"] == AGENT_NAME

    @pytest.mark.asyncio
    async def test_existing_errors_preserved_on_new_error(self) -> None:
        ado = MagicMock()
        ado.repository = "repo"
        ado.get_latest_commit_sha = AsyncMock(side_effect=RuntimeError("fail"))
        ado.get_file_content = AsyncMock(return_value=None)
        state = _make_state(errors=["prior-error"])
        node = make_code_context_node(ado_client=ado)
        result = await node(state)
        assert "prior-error" in result["errors"]
