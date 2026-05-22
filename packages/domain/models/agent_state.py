from typing import Any, TypedDict


class IncidentState(TypedDict, total=False):
    # Core incident — required at pipeline entry
    incident_id: str
    correlation_id: str
    exception_type: str
    exception_message: str
    stack_trace: str
    raw_payload: dict[str, Any]

    # Triage outputs
    priority: str | None
    triage_labels: list[str]
    group_id: str | None

    # Root cause outputs
    root_cause_summary: str | None
    root_cause_json: dict[str, Any] | None

    # Code context outputs
    code_snippets: list[dict[str, Any]]

    # RAG outputs
    rag_results: list[dict[str, Any]]

    # Fix planner outputs
    recommendations: list[dict[str, Any]]

    # Bug creation outputs
    ado_bug_id: int | None
    ado_bug_url: str | None

    # Phase 2 — PR generation
    pr_branch: str | None
    pr_url: str | None
    validation_report: dict[str, Any] | None

    # Audit
    agent_trace: list[dict[str, Any]]
    errors: list[str]
