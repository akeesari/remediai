"""Unit tests for validation agent node behavior."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from packages.agent_runtime.validation_agent.agent import make_validation_agent_node
from packages.domain.models.agent_state import IncidentState


class _FakeLLM:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    async def ainvoke(self, _: object) -> Any:
        return SimpleNamespace(content=json.dumps(self._payload))


class _FakePrReader:
    def __init__(self, diff_text: str) -> None:
        self.diff_text = diff_text
        self.appended_reports: list[tuple[int, str]] = []

    async def get_pr_diff(self, pr_id: int) -> str:
        assert pr_id == 123
        return self.diff_text

    async def append_validation_report(self, pr_id: int, report_markdown: str) -> None:
        self.appended_reports.append((pr_id, report_markdown))


def _base_state() -> IncidentState:
    return {
        "incident_id": "inc-123",
        "pr_url": "https://dev.azure.com/org/proj/_git/repo/pullrequest/123",
        "root_cause_summary": "A null response is dereferenced in payment flow.",
        "approved_recommendation_rank": 1,
        "recommendations": [{"rank": 1, "title": "Add null guard"}],
        "agent_trace": [],
        "errors": [],
    }


@pytest.mark.asyncio
async def test_no_pr_url_skips_validation() -> None:
    node = make_validation_agent_node(
        llm=_FakeLLM(
            {
                "risk_level": "low",
                "confidence": 0.9,
                "llm_assessment": "Looks good.",
                "reviewer_notes": "None.",
                "concerns": [],
            }
        ),
        pr_reader=_FakePrReader(diff_text=""),
    )

    result = await node({"incident_id": "inc-1", "agent_trace": [], "errors": []})
    assert result == {}


@pytest.mark.asyncio
async def test_all_checks_pass_status_approved() -> None:
    clean_diff = """
diff --git a/src/Service.cs b/src/Service.cs
--- a/src/Service.cs
+++ b/src/Service.cs
@@ -1,3 +1,4 @@
 public class Service {
+    private readonly int _x = 1;
 }
"""
    reader = _FakePrReader(diff_text=clean_diff)
    node = make_validation_agent_node(
        llm=_FakeLLM(
            {
                "risk_level": "low",
                "confidence": 0.85,
                "llm_assessment": "Patch aligns with the root cause and remains narrow.",
                "reviewer_notes": "Confirm expected behavior in null path.",
                "concerns": [],
            }
        ),
        pr_reader=reader,
    )

    result = await node(_base_state())

    report = result["validation_report"]
    assert report["overall_status"] == "approved"
    assert report["risk_level"] == "low"
    assert len(reader.appended_reports) == 1


@pytest.mark.asyncio
async def test_secret_in_diff_blocks() -> None:
    diff = '+password = "super-secret"  # pragma: allowlist secret\n'
    reader = _FakePrReader(diff_text=diff)
    node = make_validation_agent_node(
        llm=_FakeLLM(
            {
                "risk_level": "low",
                "confidence": 0.9,
                "llm_assessment": "Should be skipped.",
                "reviewer_notes": "Should be skipped.",
                "concerns": [],
            }
        ),
        pr_reader=reader,
    )

    result = await node(_base_state())

    report = result["validation_report"]
    assert report["overall_status"] == "blocked"
    assert any(c["check_name"] == "no_secrets" and c["status"] == "fail" for c in report["checks"])


@pytest.mark.asyncio
async def test_large_diff_warns() -> None:
    diff = "\n".join(f"+line {i}" for i in range(250))
    reader = _FakePrReader(diff_text=diff)
    node = make_validation_agent_node(
        llm=_FakeLLM(
            {
                "risk_level": "medium",
                "confidence": 0.7,
                "llm_assessment": "Scope is broad and needs manual review.",
                "reviewer_notes": "Inspect changed sections carefully.",
                "concerns": ["Large change set"],
            }
        ),
        pr_reader=reader,
    )

    result = await node(_base_state())
    report = result["validation_report"]

    diff_size_check = next(c for c in report["checks"] if c["check_name"] == "diff_size")
    assert diff_size_check["status"] == "warn"


@pytest.mark.asyncio
async def test_validation_report_written_to_state() -> None:
    clean_diff = """
diff --git a/src/Service.cs b/src/Service.cs
--- a/src/Service.cs
+++ b/src/Service.cs
@@ -1,2 +1,2 @@
-public class Service {}
+public class Service { }
"""
    reader = _FakePrReader(diff_text=clean_diff)
    node = make_validation_agent_node(
        llm=_FakeLLM(
            {
                "risk_level": "low",
                "confidence": 0.8,
                "llm_assessment": "Change is minimal and consistent with recommendation.",
                "reviewer_notes": "Confirm style checks in CI.",
                "concerns": [],
            }
        ),
        pr_reader=reader,
    )

    result = await node(_base_state())

    assert "validation_report" in result
    assert result["validation_report"]["llm_assessment"]
    assert any(entry["agent_name"] == "validation_agent" for entry in result["agent_trace"])
