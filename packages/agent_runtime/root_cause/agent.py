from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from packages.agent_runtime.root_cause.models import RootCauseJson, RootCauseOutput
from packages.agent_runtime.root_cause.prompt import load_root_cause_prompt
from packages.agent_runtime.root_cause.stack_parser import parse_stack_frames
from packages.agent_runtime.utils import agent_trace_ctx, parse_llm_json_response
from packages.domain.models.agent_state import IncidentState
from packages.integrations.pii_scrubber import scrub

logger = structlog.get_logger()

AGENT_NAME = "root_cause"
PROMPT_VERSION = "root_cause_v2"

# Dependency files to try fetching from the repo root (Gap 3)
_DEPENDENCY_FILES: list[str] = [
    "requirements.txt",
    "pyproject.toml",
    "package.json",
    "pom.xml",
]
_MAX_DEP_CHARS = 500
_MAX_COMMITS_PER_FILE = 5


class ADOClientProtocol(Protocol):
    """Minimal interface required for commit and dependency context fetching."""

    async def get_file_content(self, file_path: str) -> str | None: ...

    async def get_recent_commits(self, file_path: str, top: int = 5) -> list[dict[str, str]]: ...


_DEFAULT_OUTPUT = RootCauseOutput(
    root_cause_summary="Root cause analysis failed; manual review required.",
    root_cause_json=RootCauseJson(
        component="unknown",
        likely_cause="insufficient_evidence",
        contributing_factors=[],
        confidence=0.0,
    ),
    evidence=[],
)


def make_root_cause_node(
    llm: BaseChatModel,
    ado_client: Any = None,
    settings: Any = None,
) -> Callable[[IncidentState], Awaitable[dict[str, Any]]]:
    """Return an async LangGraph node that performs root cause analysis.

    When *ado_client* is provided (or resolvable from *settings*), the agent
    fetches recent commits and dependency files before calling the LLM.
    """

    async def root_cause_node(state: IncidentState) -> dict[str, Any]:
        exception_type: str = state.get("exception_type", "")
        exception_message: str = state.get("exception_message", "")
        stack_trace: str = state.get("stack_trace", "") or ""
        incident_id: str = state.get("incident_id", "")

        log = logger.bind(agent=AGENT_NAME, incident_id=incident_id)
        log.info("root_cause_start", exception_type=exception_type)

        frames = parse_stack_frames(stack_trace)
        top_frames = [f.method for f in frames]
        file_paths = list({f.file_path for f in frames if f.file_path})

        # Gap 3 — fetch additional evidence from source control when available
        recent_commits: list[dict[str, Any]] = []
        dependency_context: str | None = None

        client = await _resolve_client(ado_client, settings)
        if client is not None:
            recent_commits, dependency_context = await _fetch_context(client, file_paths, log)

        with agent_trace_ctx(AGENT_NAME, state) as ctx:
            try:
                output = await _call_llm(llm, state, top_frames, recent_commits, dependency_context)
                log.info(
                    "root_cause_complete",
                    component=output.root_cause_json.component,
                    confidence=output.root_cause_json.confidence,
                    commits_used=len(recent_commits),
                    deps_used=dependency_context is not None,
                )
            except Exception as exc:
                log.error("root_cause_llm_failed", error=str(exc))
                ctx.error = str(exc)
                output = _DEFAULT_OUTPUT

            return ctx.build(
                prompt_version=PROMPT_VERSION,
                input_summary=(
                    f"type={exception_type}, "
                    f"msg={scrub(exception_message)[:100]}, "
                    f"frames={len(top_frames)}, "
                    f"commits={len(recent_commits)}"
                ),
                output_summary=(
                    f"component={output.root_cause_json.component}, "
                    f"confidence={output.root_cause_json.confidence}"
                ),
                root_cause_summary=output.root_cause_summary,
                root_cause_json=output.root_cause_json.model_dump(),
                recent_commits=recent_commits,
                dependency_context=dependency_context,
            )

    return root_cause_node


async def _fetch_context(
    client: ADOClientProtocol,
    file_paths: list[str],
    log: Any,
) -> tuple[list[dict[str, Any]], str | None]:
    """Fetch recent commits for affected files and dependency file snippets."""
    recent_commits: list[dict[str, Any]] = []

    # Recent commits for top 2 affected files (avoids too many API calls)
    for fp in file_paths[:2]:
        try:
            commits = await client.get_recent_commits(fp, top=_MAX_COMMITS_PER_FILE)
            for c in commits:
                recent_commits.append({"file_path": fp, **c})
        except Exception as exc:
            log.debug("root_cause_commits_fetch_failed", file=fp, error=str(exc))

    # Dependency files
    dep_parts: list[str] = []
    for dep_file in _DEPENDENCY_FILES:
        try:
            content = await client.get_file_content(dep_file)
            if content:
                snippet = content[:_MAX_DEP_CHARS]
                dep_parts.append(f"=== {dep_file} ===\n{snippet}")
        except Exception as exc:
            log.debug("root_cause_dep_fetch_failed", file=dep_file, error=str(exc))

    dependency_context = "\n\n".join(dep_parts) if dep_parts else None
    return recent_commits, dependency_context


async def _call_llm(
    llm: BaseChatModel,
    state: IncidentState,
    top_frames: list[str],
    recent_commits: list[dict[str, Any]],
    dependency_context: str | None,
) -> RootCauseOutput:
    system_prompt = load_root_cause_prompt()
    log = logger.bind(agent=AGENT_NAME, incident_id=state.get("incident_id", ""))
    log.debug("pii_scrub_applied", fields_scrubbed=["exception_message", "stack_trace"])

    payload: dict[str, Any] = {
        "incident_id": state.get("incident_id", ""),
        "exception_type": state.get("exception_type", ""),
        "exception_message": scrub(state.get("exception_message", "") or ""),
        "stack_trace": scrub((state.get("stack_trace", "") or "")[:2000]),
        "triage_labels": state.get("triage_labels", []),
        "top_stack_frames": top_frames,
        "exception_language": state.get("exception_language") or "unknown",
    }
    if recent_commits:
        payload["recent_commits"] = recent_commits
    if dependency_context:
        payload["dependency_snapshot"] = dependency_context

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
    ]
    response = await llm.ainvoke(messages)

    data = parse_llm_json_response(str(response.content))
    return RootCauseOutput.model_validate(data)


async def _resolve_client(
    ado_client: ADOClientProtocol | None,
    settings: Any,
) -> ADOClientProtocol | None:
    if ado_client is not None:
        return ado_client
    try:
        from packages.config.settings import get_settings
        from packages.integrations.azure_devops.client import AzureDevOpsClient
        from packages.integrations.providers.registry import resolve_scm_provider_id

        s = settings or get_settings()
        if resolve_scm_provider_id(s) != "azure-devops":
            return None
        if not getattr(s, "azure_devops_org_url", ""):
            return None
        return AzureDevOpsClient.from_settings(s)
    except Exception:
        return None
