from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

import structlog

from packages.agent_runtime.code_context.frame_filter import filter_frames
from packages.agent_runtime.code_context.models import CodeSnippet
from packages.agent_runtime.root_cause.stack_parser import parse_stack_frames
from packages.domain.models.agent_state import IncidentState
from packages.domain.models.audit import AgentTraceEntry

logger = structlog.get_logger()

AGENT_NAME = "code_context"
_CONTEXT_LINES = 20
_MAX_SNIPPETS = 5


class ADOClientProtocol(Protocol):
    """Minimal interface required by the code context agent."""

    repository: str

    async def get_file_content(self, file_path: str) -> str | None: ...

    async def get_latest_commit_sha(self) -> str: ...


def make_code_context_node(
    ado_client: ADOClientProtocol | None = None,
    settings: Any = None,
) -> Callable[[IncidentState], Awaitable[dict[str, Any]]]:
    """Return an async LangGraph node that fetches source snippets from Azure DevOps Repos."""

    async def code_context_node(state: IncidentState) -> dict[str, Any]:
        start_ms = int(time.monotonic() * 1000)
        incident_id: str = state.get("incident_id", "")
        stack_trace: str = state.get("stack_trace", "") or ""

        log = logger.bind(agent=AGENT_NAME, incident_id=incident_id)
        log.info("code_context_start")

        client = await _resolve_client(ado_client, settings)
        error: str | None = None
        snippets: list[CodeSnippet] = []

        try:
            commit_sha = await client.get_latest_commit_sha()
            frames = parse_stack_frames(stack_trace)
            path_prefix: str = (
                getattr(settings, "ado_source_path_prefix", "") if settings is not None else ""
            )
            qualifying = filter_frames(frames, path_prefix=path_prefix)

            for frame in qualifying[:_MAX_SNIPPETS]:
                content = await client.get_file_content(frame.file_path)  # type: ignore[arg-type]
                if content is None:
                    log.debug("code_context_file_not_found", path=frame.file_path)
                    continue
                snippet = _build_snippet(
                    content=content,
                    file_path=frame.file_path,  # type: ignore[arg-type]
                    line_number=frame.line_number,  # type: ignore[arg-type]
                    repo=client.repository,
                    commit_sha=commit_sha,
                )
                snippets.append(snippet)

            log.info("code_context_complete", snippets_fetched=len(snippets))
        except Exception as exc:
            log.error("code_context_failed", error=str(exc))
            error = str(exc)
        finally:
            if ado_client is None and hasattr(client, "aclose"):
                await client.aclose()

        latency_ms = int(time.monotonic() * 1000) - start_ms
        trace_entry = AgentTraceEntry(
            agent_name=AGENT_NAME,
            prompt_version=None,
            input_summary=f"stack_trace_len={len(stack_trace)}",
            output_summary=f"snippets={len(snippets)}",
            latency_ms=latency_ms,
            error=error,
        )

        existing_trace: list[dict[str, Any]] = list(state.get("agent_trace", []))
        existing_errors: list[str] = list(state.get("errors", []))
        if error:
            existing_errors.append(f"{AGENT_NAME}: {error}")

        return {
            "code_snippets": [s.model_dump() for s in snippets],
            "agent_trace": existing_trace + [trace_entry.model_dump()],
            "errors": existing_errors,
        }

    return code_context_node


async def _resolve_client(
    ado_client: ADOClientProtocol | None,
    settings: Any,
) -> ADOClientProtocol:
    if ado_client is not None:
        return ado_client
    from apps.api.core.config import get_settings
    from packages.integrations.azure_devops.client import AzureDevOpsClient

    s = settings or get_settings()
    return AzureDevOpsClient.from_settings(s)


def _build_snippet(
    content: str,
    file_path: str,
    line_number: int,
    repo: str,
    commit_sha: str,
) -> CodeSnippet:
    lines = content.splitlines()
    total = len(lines)
    # 0-indexed slice
    start_idx = max(0, line_number - 1 - _CONTEXT_LINES)
    end_idx = min(total, line_number + _CONTEXT_LINES)
    return CodeSnippet(
        file_path=file_path,
        start_line=start_idx + 1,
        end_line=end_idx,
        content="\n".join(lines[start_idx:end_idx]),
        repo=repo,
        commit_sha=commit_sha,
    )
