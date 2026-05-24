"""Unit tests for the Phase 19 PR agent."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from packages.agent_runtime.pr_agent.agent import make_pr_agent_node
from packages.domain.models.agent_state import IncidentState


class _FakeLLM:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    async def ainvoke(self, _: object) -> Any:
        return SimpleNamespace(content=json.dumps(self._payload))


class _FakeWriter:
    def __init__(self) -> None:
        self.repository = "repo"
        self.default_branch = "main"
        self.branch_calls: list[tuple[str, str]] = []
        self.push_calls: list[tuple[str, str, str, str]] = []
        self.pr_calls: list[dict[str, object]] = []

    async def create_branch(self, branch_name: str, from_sha: str) -> None:
        self.branch_calls.append((branch_name, from_sha))

    async def get_latest_commit_sha(self) -> str:
        return "a" * 40

    async def push_patch(
        self, branch: str, file_path: str, content: str, commit_message: str
    ) -> None:
        self.push_calls.append((branch, file_path, content, commit_message))

    async def create_pull_request(
        self,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str,
        is_draft: bool,
    ) -> dict[str, Any]:
        self.pr_calls.append(
            {
                "source_branch": source_branch,
                "target_branch": target_branch,
                "title": title,
                "description": description,
                "is_draft": is_draft,
            }
        )
        return {
            "pullRequestId": 123,
            "_links": {"web": {"href": "https://dev.azure.com/org/proj/_git/repo/pullrequest/123"}},
        }


def _base_state() -> IncidentState:
    return {
        "incident_id": "12345678-1234-1234-1234-1234567890ab",
        "approval_status": "approved",
        "approved_recommendation_rank": 1,
        "root_cause_summary": "A null response is dereferenced in payment flow.",
        "recommendations": [
            {
                "rank": 1,
                "title": "Add null guard",
                "description": "Check response for null before dereference.",
                "affected_files": ["src/PaymentService.cs"],
                "suggested_change": "Add a null guard around gateway response usage.",
            }
        ],
        "code_snippets": [
            {
                "file_path": "src/PaymentService.cs",
                "content": "public class PaymentService {\n  public void Run() {\n    var x = gateway.Get();\n    Console.WriteLine(x.Value);\n  }\n}\n",
            }
        ],
        "agent_trace": [],
        "errors": [],
    }


@pytest.mark.asyncio
async def test_approved_incident_creates_branch() -> None:
    llm = _FakeLLM(
        {
            "patched_content": "public class PaymentService {\n  public void Run() {\n    var x = gateway.Get();\n    if (x == null) return;\n    Console.WriteLine(x.Value);\n  }\n}\n",
            "files_changed": ["src/PaymentService.cs"],
        }
    )
    writer = _FakeWriter()
    node = make_pr_agent_node(llm=llm, ado_writer=writer)

    await node(_base_state())

    assert len(writer.branch_calls) == 1
    assert writer.branch_calls[0][0] == "remedia/12345678/1"


@pytest.mark.asyncio
async def test_approved_incident_creates_draft_pr() -> None:
    llm = _FakeLLM(
        {
            "patched_content": "public class PaymentService {\n  public void Run() {\n    var x = gateway.Get();\n    if (x == null) return;\n    Console.WriteLine(x.Value);\n  }\n}\n",
            "files_changed": ["src/PaymentService.cs"],
        }
    )
    writer = _FakeWriter()
    node = make_pr_agent_node(llm=llm, ado_writer=writer)

    await node(_base_state())

    assert len(writer.pr_calls) == 1
    assert writer.pr_calls[0]["is_draft"] is True


@pytest.mark.asyncio
async def test_pr_url_written_to_state() -> None:
    llm = _FakeLLM(
        {
            "patched_content": "public class PaymentService {\n  public void Run() {\n    var x = gateway.Get();\n    if (x == null) return;\n    Console.WriteLine(x.Value);\n  }\n}\n",
            "files_changed": ["src/PaymentService.cs"],
        }
    )
    writer = _FakeWriter()
    node = make_pr_agent_node(llm=llm, ado_writer=writer)

    result = await node(_base_state())

    assert result["pr_url"]


@pytest.mark.asyncio
async def test_unapproved_incident_skips_pr() -> None:
    llm = _FakeLLM(
        {
            "patched_content": "unchanged",
            "files_changed": ["src/PaymentService.cs"],
        }
    )
    writer = _FakeWriter()
    node = make_pr_agent_node(llm=llm, ado_writer=writer)

    state = _base_state()
    state["approval_status"] = "rejected"
    result = await node(state)

    assert writer.branch_calls == []
    assert writer.pr_calls == []
    assert result["errors"] == []


@pytest.mark.asyncio
async def test_patch_too_large_sets_error() -> None:
    original = "\n".join(f"line {i}" for i in range(700)) + "\n"
    patched = "\n".join(f"changed {i}" for i in range(700)) + "\n"
    llm = _FakeLLM(
        {
            "patched_content": patched,
            "files_changed": ["src/PaymentService.cs"],
        }
    )
    writer = _FakeWriter()
    node = make_pr_agent_node(llm=llm, ado_writer=writer)

    state = _base_state()
    state["code_snippets"] = [{"file_path": "src/PaymentService.cs", "content": original}]
    result = await node(state)

    assert any("exceeds the 500-line limit" in e for e in result["errors"])
    assert result["pr_url"]
    assert writer.push_calls == []
