from typing import Any, TypedDict


class IncidentState(TypedDict, total=False):
    # Core incident — required at pipeline entry
    incident_id: str
    correlation_id: str
    exception_type: str
    exception_message: str
    stack_trace: str
    raw_payload: dict[str, Any]
    # Phase 36 — detected language: dotnet | python | nodejs | java | unknown
    exception_language: str | None

    # Optional: target ADO repository for this incident.
    # When set, the PR agent routes to this repo instead of the static
    # AZURE_DEVOPS_REPOSITORY setting — enables multi-project support.
    ado_repository: str | None

    # Triage outputs
    priority: str | None
    triage_labels: list[str]
    group_id: str | None

    # Phase 19 — approval gate
    approval_status: str | None  # None | "approved" | "rejected"
    approved_recommendation_rank: int | None

    # Root cause outputs
    root_cause_summary: str | None
    root_cause_json: dict[str, Any] | None
    # Gap 3 — recent git commits and dependency file snapshot for affected files
    recent_commits: list[dict[str, Any]]
    dependency_context: str | None

    # Code context outputs
    code_snippets: list[dict[str, Any]]

    # RAG outputs
    rag_results: list[dict[str, Any]]

    # Fix planner outputs
    recommendations: list[dict[str, Any]]

    # Bug creation outputs
    ado_bug_id: int | None
    ado_bug_url: str | None

    # Phase 35 — code fix generation (set by code_fix agent before pr_agent)
    code_fix_result: dict[str, Any] | None

    # Phase 2 — PR generation
    pr_branch: str | None
    pr_url: str | None
    validation_report: dict[str, Any] | None

    # Audit
    agent_trace: list[dict[str, Any]]
    errors: list[str]
