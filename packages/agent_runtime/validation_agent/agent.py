from __future__ import annotations

import json
import re
import time
from collections.abc import Awaitable, Callable
from typing import Any, Literal, Protocol, cast

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from packages.agent_runtime.prompt_registry import get_registry
from packages.agent_runtime.validation_agent.models import ValidationCheck, ValidationReport
from packages.agent_runtime.validation_agent.static_checks import has_fail_checks, run_static_checks
from packages.domain.models.agent_state import IncidentState
from packages.domain.models.audit import AgentTraceEntry
from packages.integrations.pii_scrubber import scrub

logger = structlog.get_logger()

AGENT_NAME = "validation_agent"
PROMPT_VERSION = "validation_v1"
_MAX_LLM_DIFF_LINES = 300


class ADOPrReaderProtocol(Protocol):
    async def get_pr_diff(self, pr_id: int) -> str: ...

    async def append_validation_report(self, pr_id: int, report_markdown: str) -> None: ...


def make_validation_agent_node(
    llm: BaseChatModel | None = None,
    pr_reader: ADOPrReaderProtocol | None = None,
    settings: Any = None,
) -> Callable[[IncidentState], Awaitable[dict[str, Any]]]:
    """Return an async LangGraph node that validates PR diffs after PR creation."""

    async def validation_agent_node(state: IncidentState) -> dict[str, Any]:
        start_ms = int(time.monotonic() * 1000)
        pr_url = state.get("pr_url")
        if not pr_url:
            # No-op by design when PR was not created.
            return {}

        incident_id = state.get("incident_id", "")
        log = logger.bind(agent=AGENT_NAME, incident_id=incident_id, pr_url=pr_url)
        log.info("validation_agent_start")

        existing_trace: list[dict[str, Any]] = list(state.get("agent_trace", []))
        existing_errors: list[str] = list(state.get("errors", []))

        reader = _resolve_reader(pr_reader, settings)
        if reader is None:
            latency_ms = int(time.monotonic() * 1000) - start_ms
            trace_entry = AgentTraceEntry(
                agent_name=AGENT_NAME,
                prompt_version=None,
                input_summary=f"pr_url={pr_url}",
                output_summary="skipped - scm integration not configured",
                latency_ms=latency_ms,
                error=None,
            )
            return {
                "agent_trace": existing_trace + [trace_entry.model_dump()],
                "errors": existing_errors,
            }

        resolved_llm = _resolve_llm(llm, settings)
        error: str | None = None
        report: ValidationReport | None = None

        try:
            pr_id = _extract_pr_id(str(pr_url))
            diff_text = await reader.get_pr_diff(pr_id)
            checks = run_static_checks(diff_text)

            if has_fail_checks(checks):
                report = ValidationReport(
                    overall_status="blocked",
                    checks=checks,
                    llm_assessment="Static validation failed; LLM review skipped.",
                    risk_level="high",
                    confidence=1.0,
                    reviewer_notes="Resolve failed checks before considering merge.",
                )
            else:
                llm_payload = await _call_llm(
                    llm=resolved_llm,
                    state=state,
                    diff_text=diff_text,
                )
                report = _build_report_from_llm(checks=checks, llm_payload=llm_payload)

            await reader.append_validation_report(pr_id, _render_report_markdown(report))
            log.info(
                "validation_agent_complete",
                overall_status=report.overall_status,
                risk_level=report.risk_level,
            )

        except Exception as exc:
            error = str(exc)
            existing_errors.append(f"{AGENT_NAME}: {error}")
            log.error("validation_agent_failed", error=error)

        latency_ms = int(time.monotonic() * 1000) - start_ms
        trace_entry = AgentTraceEntry(
            agent_name=AGENT_NAME,
            prompt_version=PROMPT_VERSION,
            input_summary=f"pr_url={pr_url}",
            output_summary=(
                f"overall_status={report.overall_status}, risk={report.risk_level}"
                if report
                else "failed"
            ),
            latency_ms=latency_ms,
            error=error,
        )

        result: dict[str, Any] = {
            "agent_trace": existing_trace + [trace_entry.model_dump()],
            "errors": existing_errors,
        }
        if report:
            result["validation_report"] = report.model_dump()
        return result

    return validation_agent_node


def _resolve_reader(
    pr_reader: ADOPrReaderProtocol | None, settings: Any
) -> ADOPrReaderProtocol | None:
    if pr_reader is not None:
        return pr_reader
    from apps.api.core.config import get_settings
    from packages.integrations.azure_devops.pr_reader import ADOPrReader
    from packages.integrations.providers.registry import resolve_scm_provider_id

    s = settings or get_settings()
    provider_id = resolve_scm_provider_id(s)
    if provider_id != "azure-devops":
        return None
    if not getattr(s, "azure_devops_org_url", ""):
        return None
    return ADOPrReader.from_settings(s)


def _resolve_llm(llm: BaseChatModel | None, settings: Any) -> BaseChatModel:
    if llm is not None:
        return llm
    from apps.api.core.config import get_settings
    from packages.integrations.providers.registry import (
        create_chat_model,
        ensure_valid_provider_config,
    )

    s = settings or get_settings()
    ensure_valid_provider_config(s)
    return create_chat_model(s)


def _extract_pr_id(pr_url: str) -> int:
    match = re.search(r"(?:pullrequest[s]?/)(\d+)$", pr_url)
    if not match:
        match = re.search(r"(\d+)$", pr_url)
    if not match:
        raise ValueError(f"Unable to extract PR id from URL: {pr_url}")
    return int(match.group(1))


async def _call_llm(
    llm: BaseChatModel,
    state: IncidentState,
    diff_text: str,
) -> dict[str, Any]:
    system_prompt = get_registry().load("validation", "1")
    recommendation_title = _approved_recommendation_title(state)
    logger.bind(agent=AGENT_NAME).debug(
        "pii_scrub_applied",
        fields_scrubbed=["root_cause_summary", "recommendation_title"],
    )

    truncated_diff = "\n".join(diff_text.splitlines()[:_MAX_LLM_DIFF_LINES])
    user_content = json.dumps(
        {
            "root_cause_summary": scrub(state.get("root_cause_summary", "") or ""),
            "recommendation_title": scrub(recommendation_title),
            "diff": truncated_diff,
        },
        ensure_ascii=False,
    )

    response = await llm.ainvoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content),
        ]
    )

    content = str(response.content).strip()
    if content.startswith("```"):
        parts = content.split("```")
        content = parts[1] if len(parts) > 1 else content
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    return cast(dict[str, Any], json.loads(content))


def _approved_recommendation_title(state: IncidentState) -> str:
    rank = state.get("approved_recommendation_rank")
    recommendations = state.get("recommendations", [])
    if rank and 0 < rank <= len(recommendations):
        recommendation = recommendations[rank - 1]
        if isinstance(recommendation, dict):
            return str(recommendation.get("title", ""))
    if recommendations and isinstance(recommendations[0], dict):
        return str(recommendations[0].get("title", ""))
    return ""


def _build_report_from_llm(
    *,
    checks: list[ValidationCheck],
    llm_payload: dict[str, Any],
) -> ValidationReport:
    risk_level = str(llm_payload.get("risk_level", "medium")).lower()
    if risk_level not in {"low", "medium", "high"}:
        risk_level = "medium"
    risk_level_literal = cast(Literal["low", "medium", "high"], risk_level)

    confidence = float(llm_payload.get("confidence", 0.0))
    has_warn = any(check.status == "warn" for check in checks)

    if not has_warn and risk_level == "low" and confidence >= 0.75:
        overall_status = "approved"
    else:
        overall_status = "needs_review"
    overall_status_literal = cast(Literal["approved", "needs_review", "blocked"], overall_status)

    return ValidationReport(
        overall_status=overall_status_literal,
        checks=checks,
        llm_assessment=str(llm_payload.get("llm_assessment", "Manual review recommended.")),
        risk_level=risk_level_literal,
        confidence=confidence,
        reviewer_notes=str(llm_payload.get("reviewer_notes", "Review the patch in detail.")),
    )


def _render_report_markdown(report: ValidationReport) -> str:
    status_icon = {
        "approved": "✅ Approved",
        "needs_review": "⚠️ Needs Review",
        "blocked": "🚫 Blocked",
    }[report.overall_status]
    risk_text = report.risk_level.capitalize()
    confidence_pct = int(round(report.confidence * 100))

    check_lines = []
    for check in report.checks:
        icon = {"pass": "✅", "warn": "⚠️", "fail": "🚫"}[check.status]
        check_lines.append(f"- {icon} {check.detail}")

    return "\n".join(
        [
            "---",
            "## RemediAI Validation Report",
            "",
            f"**Status:** {status_icon}",
            f"**Risk:** {risk_text}",
            f"**Confidence:** {confidence_pct}%",
            "",
            "### Checks",
            *check_lines,
            "",
            "### Assessment",
            report.llm_assessment,
            "",
            "### Reviewer Notes",
            report.reviewer_notes,
            "",
            "*Generated by RemediAI Validation Agent — human review required before merge.*",
        ]
    )
