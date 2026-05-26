from __future__ import annotations

import json
import time
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from packages.agent_runtime.pr_agent.models import PRAgentOutput
from packages.agent_runtime.pr_agent.patch_builder import PatchTooLargeError, build_patch
from packages.agent_runtime.prompt_registry import get_registry
from packages.agent_runtime.utils import parse_llm_json_response
from packages.domain.models.agent_state import IncidentState
from packages.domain.models.audit import AgentTraceEntry
from packages.integrations.pii_scrubber import scrub

logger = structlog.get_logger()

AGENT_NAME = "pr_agent"
PROMPT_VERSION = "pr_patch_v1"
_BRANCH_PREFIX = "remedia"


class ADOReposWriterProtocol(Protocol):
    """Minimal interface required by the PR agent."""

    repository: str
    default_branch: str

    async def create_branch(self, branch_name: str, from_sha: str) -> None: ...

    async def get_latest_commit_sha(self) -> str: ...

    async def push_patch(
        self, branch: str, file_path: str, content: str, commit_message: str
    ) -> None: ...

    async def create_pull_request(
        self,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str,
        is_draft: bool,
    ) -> dict[str, Any]: ...


def make_pr_agent_node(
    llm: BaseChatModel | None = None,
    ado_writer: ADOReposWriterProtocol | None = None,
    settings: Any = None,
) -> Callable[[IncidentState], Awaitable[dict[str, Any]]]:
    """Return an async LangGraph node that creates a draft PR from an approved recommendation."""

    async def pr_agent_node(state: IncidentState) -> dict[str, Any]:
        start_ms = int(time.monotonic() * 1000)
        incident_id: str = state.get("incident_id", "")
        approval_status: str | None = state.get("approval_status")
        approved_rank: int | None = state.get("approved_recommendation_rank")

        log = logger.bind(agent=AGENT_NAME, incident_id=incident_id)
        log.info("pr_agent_start", approval_status=approval_status)

        existing_trace: list[dict[str, Any]] = list(state.get("agent_trace", []))
        existing_errors: list[str] = list(state.get("errors", []))

        # Guard: only run when explicitly approved
        if approval_status != "approved" or approved_rank is None:
            log.info("pr_agent_skipped", reason="not_approved")
            latency_ms = int(time.monotonic() * 1000) - start_ms
            trace_entry = AgentTraceEntry(
                agent_name=AGENT_NAME,
                prompt_version=None,
                input_summary=f"approval_status={approval_status}",
                output_summary="skipped — not approved",
                latency_ms=latency_ms,
                error=None,
            )
            return {
                "agent_trace": existing_trace + [trace_entry.model_dump()],
                "errors": existing_errors,
            }

        recommendations: list[dict[str, Any]] = state.get("recommendations", [])
        if not recommendations or approved_rank > len(recommendations):
            error_msg = f"approved_recommendation_rank {approved_rank} out of range"
            existing_errors.append(f"{AGENT_NAME}: {error_msg}")
            latency_ms = int(time.monotonic() * 1000) - start_ms
            trace_entry = AgentTraceEntry(
                agent_name=AGENT_NAME,
                prompt_version=PROMPT_VERSION,
                input_summary=f"rank={approved_rank}",
                output_summary="error: rank out of range",
                latency_ms=latency_ms,
                error=error_msg,
            )
            return {
                "agent_trace": existing_trace + [trace_entry.model_dump()],
                "errors": existing_errors,
            }

        recommendation = recommendations[approved_rank - 1]
        affected_files: list[str] = recommendation.get("affected_files", [])
        file_path: str = affected_files[0] if affected_files else ""

        writer = _resolve_writer(ado_writer, settings)
        if writer is None:
            log.info("pr_agent_skipped", reason="scm_not_configured")
            latency_ms = int(time.monotonic() * 1000) - start_ms
            trace_entry = AgentTraceEntry(
                agent_name=AGENT_NAME,
                prompt_version=None,
                input_summary=f"rank={approved_rank}, file={file_path}",
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
        output: PRAgentOutput | None = None

        try:
            # Resolve code snippet for the affected file (if fetched in previous step)
            original_content = _find_snippet_content(state, file_path)

            # Call LLM to refine suggested_change into patched file content
            patched_content, files_changed = await _call_llm(
                resolved_llm, recommendation, original_content, file_path
            )

            patch_applied = False
            if original_content and patched_content and patched_content != original_content:
                try:
                    build_patch(original_content, patched_content, file_path)
                    patch_applied = True
                except PatchTooLargeError as exc:
                    error = str(exc)
                    existing_errors.append(f"{AGENT_NAME}: {error}")
                    patch_applied = False

            # Create branch
            branch_name = f"{_BRANCH_PREFIX}/{incident_id[:8]}/{approved_rank}"
            head_sha = await writer.get_latest_commit_sha()
            await writer.create_branch(branch_name=branch_name, from_sha=head_sha)

            # Push file change when patch applies cleanly
            if patch_applied and file_path and patched_content:
                await writer.push_patch(
                    branch=branch_name,
                    file_path=file_path,
                    content=patched_content,
                    commit_message=f"[RemediAI] {recommendation.get('title', 'Apply fix')}",
                )

            # Create draft PR (never auto-complete)
            root_cause_summary: str = state.get("root_cause_summary", "") or ""
            description = _build_pr_description(
                root_cause_summary=root_cause_summary,
                recommendation=recommendation,
                patch_applied=patch_applied,
            )
            pr_data = await writer.create_pull_request(
                source_branch=branch_name,
                target_branch=writer.default_branch,
                title=f"[RemediAI] {recommendation.get('title', 'Incident fix')}",
                description=description,
                is_draft=True,
            )

            pr_id: int = int(pr_data.get("pullRequestId", 0))
            pr_url_val = (
                pr_data.get("url") or pr_data.get("_links", {}).get("web", {}).get("href", "") or ""
            )

            output = PRAgentOutput(
                pr_branch=branch_name,
                pr_url=str(pr_url_val),
                pr_id=pr_id,
                patch_applied=patch_applied,
                files_changed=files_changed,
            )
            log.info(
                "pr_agent_complete",
                pr_id=pr_id,
                branch=branch_name,
                patch_applied=patch_applied,
            )

        except Exception as exc:
            log.error("pr_agent_failed", error=str(exc))
            error = str(exc)
            existing_errors.append(f"{AGENT_NAME}: {error}")

        latency_ms = int(time.monotonic() * 1000) - start_ms
        trace_entry = AgentTraceEntry(
            agent_name=AGENT_NAME,
            prompt_version=PROMPT_VERSION,
            input_summary=f"rank={approved_rank}, file={file_path}",
            output_summary=(
                f"pr_id={output.pr_id}, branch={output.pr_branch}" if output else "failed"
            ),
            latency_ms=latency_ms,
            error=error,
        )

        result: dict[str, Any] = {
            "agent_trace": existing_trace + [trace_entry.model_dump()],
            "errors": existing_errors,
        }
        if output:
            result["pr_branch"] = output.pr_branch
            result["pr_url"] = output.pr_url

        return result

    return pr_agent_node


def _resolve_writer(
    ado_writer: ADOReposWriterProtocol | None, settings: Any
) -> ADOReposWriterProtocol | None:
    if ado_writer is not None:
        return ado_writer
    from packages.config.settings import get_settings
    from packages.integrations.azure_devops.repos_writer import ADOReposWriter
    from packages.integrations.providers.registry import resolve_scm_provider_id

    s = settings or get_settings()
    provider_id = resolve_scm_provider_id(s)
    if provider_id != "azure-devops":
        return None
    if not getattr(s, "azure_devops_org_url", ""):
        return None
    return ADOReposWriter.from_settings(s)


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


def _find_snippet_content(state: IncidentState, file_path: str) -> str:
    """Return the code snippet content for *file_path* from state, or empty string."""
    if not file_path:
        return ""
    for snippet in state.get("code_snippets", []):
        if isinstance(snippet, dict) and snippet.get("file_path") == file_path:
            return str(snippet.get("content", ""))
    return ""


async def _call_llm(
    llm: BaseChatModel,
    recommendation: dict[str, Any],
    original_content: str,
    file_path: str,
) -> tuple[str, list[str]]:
    """Ask the LLM to produce patched file content from the recommendation."""
    system_prompt = get_registry().load("pr_patch", "1")
    suggested_change = recommendation.get("suggested_change", "")
    log = logger.bind(agent=AGENT_NAME)
    log.debug("pii_scrub_applied", fields_scrubbed=["suggested_change"])

    user_content = json.dumps(
        {
            "file_path": file_path,
            "original_content": original_content[:4000],  # source exempt from scrub per phase-15
            "suggested_change": scrub(suggested_change),
        },
        ensure_ascii=False,
    )

    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_content)]
    response = await llm.ainvoke(messages)

    data = parse_llm_json_response(str(response.content))
    patched_content = str(data.get("patched_content", original_content))
    files_changed: list[str] = list(data.get("files_changed", [file_path] if file_path else []))
    return patched_content, files_changed


def _build_pr_description(
    root_cause_summary: str,
    recommendation: dict[str, Any],
    patch_applied: bool,
) -> str:
    parts = [
        "## Root Cause",
        root_cause_summary or "See incident analysis.",
        "",
        "## Applied Fix",
        recommendation.get("description", ""),
        "",
    ]
    if not patch_applied:
        parts += [
            "> **Note:** Automatic patch could not be applied cleanly. "
            "Please review the suggested change manually.",
            "",
        ]
    parts += [
        "---",
        "_Created automatically by RemediAI. Review before merging. "
        "This PR was never set to auto-complete._",
    ]
    return "\n".join(parts)
