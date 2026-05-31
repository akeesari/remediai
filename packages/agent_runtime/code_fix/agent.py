from __future__ import annotations

import json
import time
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from packages.agent_runtime.code_fix.models import CodeFixResult
from packages.agent_runtime.prompt_registry import get_registry
from packages.agent_runtime.utils import parse_llm_json_response
from packages.domain.models.agent_state import IncidentState
from packages.domain.models.audit import AgentTraceEntry
from packages.integrations.pii_scrubber import scrub

logger = structlog.get_logger()

AGENT_NAME = "code_fix"
PROMPT_VERSION = "code_fix_v1"
_MAX_FILE_CHARS = 8_000


class ADOClientProtocol(Protocol):
    """Minimal interface required by the code fix agent."""

    repository: str

    async def get_file_content(self, file_path: str) -> str | None: ...


def make_code_fix_node(
    llm: BaseChatModel | None = None,
    ado_client: ADOClientProtocol | None = None,
    settings: Any = None,
) -> Callable[[IncidentState], Awaitable[dict[str, Any]]]:
    """Return an async LangGraph node that generates a real code patch for an approved fix."""

    async def code_fix_node(state: IncidentState) -> dict[str, Any]:
        start_ms = int(time.monotonic() * 1000)
        incident_id: str = state.get("incident_id", "")
        approval_status: str | None = state.get("approval_status")
        approved_rank: int | None = state.get("approved_recommendation_rank")

        log = logger.bind(agent=AGENT_NAME, incident_id=incident_id)
        log.info("code_fix_start", approval_status=approval_status)

        existing_trace: list[dict[str, Any]] = list(state.get("agent_trace", []))
        existing_errors: list[str] = list(state.get("errors", []))

        def _skip(reason: str, error: str | None = None) -> dict[str, Any]:
            latency_ms = int(time.monotonic() * 1000) - start_ms
            log.info("code_fix_skipped", reason=reason)
            trace = AgentTraceEntry(
                agent_name=AGENT_NAME,
                prompt_version=None,
                input_summary=f"approval_status={approval_status}",
                output_summary=f"skipped — {reason}",
                latency_ms=latency_ms,
                error=error,
            )
            result: dict[str, Any] = {
                "code_fix_result": None,
                "agent_trace": existing_trace + [trace.model_dump()],
                "errors": existing_errors,
            }
            if error:
                result["errors"] = existing_errors + [f"{AGENT_NAME}: {error}"]
            return result

        if approval_status != "approved" or approved_rank is None:
            return _skip("not_approved")

        recommendations: list[dict[str, Any]] = state.get("recommendations", [])
        if not recommendations or approved_rank > len(recommendations):
            return _skip(
                "rank_out_of_range",
                error=f"approved_recommendation_rank {approved_rank} out of range",
            )

        recommendation = recommendations[approved_rank - 1]
        file_path = _resolve_file_path(recommendation, state)

        client = await _resolve_client(ado_client, settings, state=dict(state))
        if client is None:
            return _skip("scm_not_configured")

        error: str | None = None
        fix_result: CodeFixResult | None = None

        try:
            original_content = await client.get_file_content(file_path) if file_path else None

            if original_content is None:
                log.warning("code_fix_file_not_found", file_path=file_path)
                fix_result = CodeFixResult(
                    file_path=file_path,
                    original_content="",
                    patched_content="",
                    change_summary=f"File '{file_path}' not found in repository. Manual fix required.",
                    confidence=0.0,
                    patch_applied=False,
                )
            else:
                resolved_llm = _resolve_llm(llm, settings)
                fix_result = await _call_llm(
                    llm=resolved_llm,
                    recommendation=recommendation,
                    file_path=file_path,
                    original_content=original_content,
                    root_cause_summary=state.get("root_cause_summary") or "",
                    exception_type=state.get("exception_type") or "",
                )
                if fix_result.patched_content == original_content:
                    log.info("code_fix_no_change", file_path=file_path)

        except Exception as exc:
            log.error("code_fix_failed", error=str(exc))
            error = str(exc)
            existing_errors = existing_errors + [f"{AGENT_NAME}: {error}"]
            fix_result = CodeFixResult(
                file_path=file_path,
                original_content="",
                patched_content="",
                change_summary="Code fix generation failed. Manual fix required.",
                confidence=0.0,
                patch_applied=False,
            )

        latency_ms = int(time.monotonic() * 1000) - start_ms
        trace = AgentTraceEntry(
            agent_name=AGENT_NAME,
            prompt_version=PROMPT_VERSION,
            input_summary=f"rank={approved_rank}, file={file_path}",
            output_summary=(
                f"patch_applied={fix_result.patch_applied}, confidence={fix_result.confidence:.2f}"
            )
            if fix_result
            else "failed",
            latency_ms=latency_ms,
            error=error,
        )

        return {
            "code_fix_result": fix_result.model_dump() if fix_result else None,
            "agent_trace": existing_trace + [trace.model_dump()],
            "errors": existing_errors,
        }

    return code_fix_node


async def _call_llm(
    llm: BaseChatModel,
    recommendation: dict[str, Any],
    file_path: str,
    original_content: str,
    root_cause_summary: str,
    exception_type: str,
) -> CodeFixResult:
    system_prompt = get_registry().load("code_fix", "1")
    log = logger.bind(agent=AGENT_NAME)
    log.debug(
        "pii_scrub_applied",
        fields_scrubbed=["root_cause_summary", "suggested_change", "description"],
    )

    user_content = json.dumps(
        {
            "exception_type": exception_type,
            "root_cause_summary": scrub(root_cause_summary),
            "file_path": file_path,
            "original_content": original_content[:_MAX_FILE_CHARS],
            "recommendation_title": recommendation.get("title", ""),
            "recommendation_description": scrub(recommendation.get("description", "")),
            "suggested_change": scrub(recommendation.get("suggested_change", "")),
        },
        ensure_ascii=False,
    )

    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_content)]
    response = await llm.ainvoke(messages)
    data = parse_llm_json_response(str(response.content))

    patched_content = str(data.get("patched_content", original_content))
    change_summary = str(data.get("change_summary", "No change summary provided."))
    confidence = float(data.get("confidence", 0.5))

    return CodeFixResult(
        file_path=file_path,
        original_content=original_content,
        patched_content=patched_content,
        change_summary=change_summary,
        confidence=confidence,
        patch_applied=patched_content != original_content,
    )


def _resolve_file_path(
    recommendation: dict[str, Any],
    state: IncidentState,
) -> str:
    """Return the primary file path from the recommendation or fall back to code_snippets."""
    affected: list[str] = recommendation.get("affected_files") or []
    if affected:
        return affected[0]
    snippets: list[dict[str, Any]] = state.get("code_snippets") or []
    if snippets:
        return str(snippets[0].get("file_path", ""))
    return ""


async def _resolve_client(
    ado_client: ADOClientProtocol | None,
    settings: Any,
    state: dict[str, Any] | None = None,
) -> ADOClientProtocol | None:
    if ado_client is not None:
        return ado_client
    from packages.config.settings import get_settings
    from packages.integrations.azure_devops.client import AzureDevOpsClient
    from packages.integrations.providers.registry import resolve_scm_provider_id

    s = settings or get_settings()
    provider_id = resolve_scm_provider_id(s)
    if provider_id != "azure-devops":
        return None
    if not getattr(s, "azure_devops_org_url", ""):
        return None
    return AzureDevOpsClient.from_settings(s)


def _resolve_llm(llm: BaseChatModel | None, settings: Any) -> BaseChatModel:
    if llm is not None:
        return llm
    from packages.config.settings import get_settings
    from packages.integrations.providers.registry import (
        create_chat_model,
        ensure_valid_provider_config,
    )

    s = settings or get_settings()
    ensure_valid_provider_config(s)
    return create_chat_model(s)
