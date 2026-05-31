"""Unit tests for the Code Fix Agent — LLM and ADO client are mocked throughout."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.agent_runtime.code_fix.agent import AGENT_NAME, make_code_fix_node
from packages.domain.models.agent_state import IncidentState

_ORIGINAL = "def process(x):\n    return x.value\n"
_PATCHED = "def process(x):\n    if x is None:\n        raise ValueError('x is required')\n    return x.value\n"
_CHANGE_SUMMARY = "Added None guard before accessing x.value on line 2."

_RECOMMENDATION = {
    "rank": 1,
    "title": "Add null guard",
    "description": "Add a None check before dereferencing x.",
    "affected_files": ["src/processor.py"],
    "suggested_change": "Add 'if x is None: raise ValueError' before line 2.",
    "confidence": 0.9,
    "source_refs": [],
}


def _mock_llm(patched: str = _PATCHED, summary: str = _CHANGE_SUMMARY) -> MagicMock:
    llm = MagicMock()
    llm.ainvoke = AsyncMock(
        return_value=MagicMock(
            content=f'{{"patched_content": {repr(patched)}, "change_summary": "{summary}", "confidence": 0.9}}'
        )
    )
    return llm


def _mock_ado(content: str | None = _ORIGINAL) -> MagicMock:
    ado = MagicMock()
    ado.repository = "test-repo"
    ado.get_file_content = AsyncMock(return_value=content)
    return ado


def _make_state(**overrides: object) -> IncidentState:
    base: IncidentState = {
        "incident_id": "cf-test-001",
        "correlation_id": "corr-cf",
        "exception_type": "AttributeError",
        "exception_message": "'NoneType' object has no attribute 'value'",
        "stack_trace": "  File 'src/processor.py', line 2, in process\n    return x.value",
        "raw_payload": {},
        "priority": "high",
        "triage_labels": [],
        "group_id": None,
        "approval_status": "approved",
        "approved_recommendation_rank": 1,
        "root_cause_summary": "x is None when process() is called.",
        "root_cause_json": None,
        "code_snippets": [{"file_path": "src/processor.py", "content": _ORIGINAL}],
        "rag_results": [],
        "recommendations": [_RECOMMENDATION],
        "ado_bug_id": None,
        "ado_bug_url": None,
        "code_fix_result": None,
        "pr_branch": None,
        "pr_url": None,
        "validation_report": None,
        "agent_trace": [],
        "errors": [],
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


@pytest.mark.asyncio
async def test_approved_incident_generates_patch() -> None:
    node = make_code_fix_node(llm=_mock_llm(), ado_client=_mock_ado())
    result = await node(_make_state())

    fix = result["code_fix_result"]
    assert fix is not None
    assert fix["patch_applied"] is True
    assert fix["file_path"] == "src/processor.py"
    assert fix["original_content"] == _ORIGINAL
    assert fix["patched_content"] == _PATCHED
    assert fix["change_summary"] == _CHANGE_SUMMARY
    assert fix["confidence"] == pytest.approx(0.9, abs=0.01)


@pytest.mark.asyncio
async def test_not_approved_skips_agent() -> None:
    node = make_code_fix_node(llm=_mock_llm(), ado_client=_mock_ado())
    result = await node(_make_state(approval_status=None))

    assert result["code_fix_result"] is None
    trace = result["agent_trace"]
    assert any("skipped" in str(t.get("output_summary", "")) for t in trace)


@pytest.mark.asyncio
async def test_file_not_found_sets_patch_applied_false() -> None:
    node = make_code_fix_node(llm=_mock_llm(), ado_client=_mock_ado(content=None))
    result = await node(_make_state())

    fix = result["code_fix_result"]
    assert fix is not None
    assert fix["patch_applied"] is False
    assert "not found" in fix["change_summary"].lower()


@pytest.mark.asyncio
async def test_llm_returns_unchanged_content_sets_patch_applied_false() -> None:
    node = make_code_fix_node(llm=_mock_llm(patched=_ORIGINAL), ado_client=_mock_ado())
    result = await node(_make_state())

    fix = result["code_fix_result"]
    assert fix is not None
    assert fix["patch_applied"] is False


@pytest.mark.asyncio
async def test_llm_failure_returns_safe_fallback() -> None:
    bad_llm = MagicMock()
    bad_llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

    node = make_code_fix_node(llm=bad_llm, ado_client=_mock_ado())
    result = await node(_make_state())

    fix = result["code_fix_result"]
    assert fix is not None
    assert fix["patch_applied"] is False
    assert result["errors"]


@pytest.mark.asyncio
async def test_scm_not_configured_skips_agent() -> None:
    # No ado_client and settings that resolve to no provider
    settings = MagicMock()
    settings.azure_devops_org_url = ""

    node = make_code_fix_node(llm=_mock_llm(), ado_client=None, settings=settings)

    # Patch provider resolution to return non-ADO
    import packages.agent_runtime.code_fix.agent as mod

    original = mod._resolve_client

    async def _no_client(*_a: object, **_kw: object) -> None:
        return None

    mod._resolve_client = _no_client  # type: ignore[assignment]
    try:
        result = await node(_make_state())
    finally:
        mod._resolve_client = original  # type: ignore[assignment]

    assert result["code_fix_result"] is None


@pytest.mark.asyncio
async def test_agent_trace_entry_written() -> None:
    node = make_code_fix_node(llm=_mock_llm(), ado_client=_mock_ado())
    result = await node(_make_state())

    trace = result["agent_trace"]
    assert any(t.get("agent_name") == AGENT_NAME for t in trace)


@pytest.mark.asyncio
async def test_file_path_fallback_to_code_snippets() -> None:
    """When affected_files is empty, fall back to code_snippets[0].file_path."""
    rec_no_files = {**_RECOMMENDATION, "affected_files": []}
    state = _make_state(
        recommendations=[rec_no_files],
        code_snippets=[{"file_path": "src/fallback.py", "content": _ORIGINAL}],
    )
    node = make_code_fix_node(llm=_mock_llm(), ado_client=_mock_ado())
    result = await node(state)

    fix = result["code_fix_result"]
    assert fix is not None
    assert fix["file_path"] == "src/fallback.py"
