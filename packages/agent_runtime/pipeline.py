from __future__ import annotations

from typing import Any

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, StateGraph

from packages.agent_runtime.bug_creator.agent import ADOBoardsClientProtocol, make_bug_creator_node
from packages.agent_runtime.code_context.agent import ADOClientProtocol, make_code_context_node
from packages.agent_runtime.fix_planner.agent import make_fix_planner_node
from packages.agent_runtime.pr_agent.agent import ADOReposWriterProtocol, make_pr_agent_node
from packages.agent_runtime.rag.agent import SearchClientProtocol, make_rag_node
from packages.agent_runtime.root_cause.agent import make_root_cause_node
from packages.agent_runtime.triage.agent import make_triage_node
from packages.agent_runtime.validation_agent.agent import (
    ADOPrReaderProtocol,
    make_validation_agent_node,
)
from packages.domain.models.agent_state import IncidentState

logger = structlog.get_logger()


def _pr_routing(state: IncidentState) -> str:
    """Route to pr_agent only when the incident has been explicitly approved."""
    return "pr_agent" if state.get("approval_status") == "approved" else END


def build_pipeline(
    llm: BaseChatModel | None = None,
    settings: Any = None,
    ado_client: ADOClientProtocol | None = None,
    search_client: SearchClientProtocol | None = None,
    boards_client: ADOBoardsClientProtocol | None = None,
    ado_writer: ADOReposWriterProtocol | None = None,
    pr_reader: ADOPrReaderProtocol | None = None,
) -> Any:
    """Compile and return the LangGraph incident-analysis pipeline.

    Pass *llm* explicitly in tests to inject a mock.  When omitted, an
    ``AzureChatOpenAI`` instance is constructed from *settings* (or the
    global settings singleton).

    The PR agent node is always wired in; it self-skips unless
    ``state["approval_status"] == "approved"``.
    """
    if llm is None:
        from packages.config.settings import get_settings
        from packages.integrations.providers.registry import (
            create_chat_model,
            ensure_valid_provider_config,
        )

        s = settings or get_settings()
        ensure_valid_provider_config(s)
        llm = create_chat_model(s)

    graph: StateGraph = StateGraph(IncidentState)
    graph.add_node("triage", make_triage_node(llm=llm))
    graph.add_node("root_cause", make_root_cause_node(llm=llm))
    graph.add_node(
        "code_context",
        make_code_context_node(ado_client=ado_client, settings=settings),
    )
    graph.add_node("rag", make_rag_node(search_client=search_client, settings=settings))
    graph.add_node("fix_planner", make_fix_planner_node(llm=llm))
    graph.add_node(
        "bug_creator",
        make_bug_creator_node(boards_client=boards_client, settings=settings),
    )
    graph.add_node(
        "pr_agent",
        make_pr_agent_node(llm=llm, ado_writer=ado_writer, settings=settings),
    )
    graph.add_node(
        "validation_agent",
        make_validation_agent_node(llm=llm, pr_reader=pr_reader, settings=settings),
    )

    graph.set_entry_point("triage")
    graph.add_edge("triage", "root_cause")
    graph.add_edge("root_cause", "code_context")
    graph.add_edge("code_context", "rag")
    graph.add_edge("rag", "fix_planner")
    graph.add_edge("fix_planner", "bug_creator")
    graph.add_conditional_edges("bug_creator", _pr_routing, {"pr_agent": "pr_agent", END: END})
    graph.add_edge("pr_agent", "validation_agent")
    graph.add_edge("validation_agent", END)

    return graph.compile()
