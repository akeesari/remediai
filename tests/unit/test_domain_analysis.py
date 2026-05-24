from uuid import uuid4

from packages.domain import (
    AgentTraceEntry,
    AuditLog,
    CodeSnippet,
    IncidentAnalysis,
    RAGResult,
    Recommendation,
    RootCauseJson,
    WorkItem,
    WorkItemType,
)


def test_code_snippet_construction() -> None:
    snippet = CodeSnippet(
        file_path="src/UserService.cs",
        start_line=42,
        end_line=62,
        content="public User GetById(int id) { ... }",
        repo="my-app",
        commit_sha="abc123",
    )
    assert snippet.start_line == 42
    assert snippet.repo == "my-app"


def test_rag_result_optional_url() -> None:
    result = RAGResult(
        source="runbook", title="Fix null ref", excerpt="Check for null...", relevance_score=0.91
    )
    assert result.url is None


def test_recommendation_defaults() -> None:
    rec = Recommendation(
        rank=1,
        title="Add null check",
        description="Add a null guard before accessing .Value",
        affected_files=["src/UserService.cs"],
        suggested_change="if (user == null) return null;",
        confidence=0.85,
    )
    assert rec.source_refs == []
    assert rec.rank == 1


def test_root_cause_json_construction() -> None:
    rc = RootCauseJson(
        component="UserService.GetById",
        likely_cause="Unhandled null return from DB query",
        contributing_factors=["Missing null check"],
        confidence=0.87,
    )
    assert rc.confidence == 0.87


def test_incident_analysis_empty_defaults() -> None:
    analysis = IncidentAnalysis(incident_id=uuid4())
    assert analysis.root_cause is None
    assert analysis.recommendations == []
    assert analysis.code_snippets == []
    assert analysis.rag_results == []
    assert analysis.agent_trace == []


def test_incident_analysis_with_full_data() -> None:
    trace_entry = AgentTraceEntry(
        agent_name="triage",
        input_summary="NullReferenceException in UserService",
        output_summary="priority=high, labels=[null-reference]",
        latency_ms=340,
    )
    analysis = IncidentAnalysis(
        incident_id=uuid4(),
        root_cause="Null dereference in UserService.GetById",
        agent_trace=[trace_entry],
    )
    assert len(analysis.agent_trace) == 1
    assert analysis.agent_trace[0].agent_name == "triage"


def test_agent_trace_entry_optional_fields() -> None:
    entry = AgentTraceEntry(
        agent_name="root_cause",
        input_summary="stack trace",
        output_summary="root cause summary",
        latency_ms=1200,
    )
    assert entry.prompt_version is None
    assert entry.llm_model is None
    assert entry.tokens_used is None
    assert entry.error is None


def test_audit_log_defaults() -> None:
    log = AuditLog(agent_name="triage", action="assign_priority")
    assert log.incident_id is None
    assert log.metadata == {}
    assert log.actor_identity is None


def test_work_item_defaults_to_bug() -> None:
    wi = WorkItem(
        incident_id=uuid4(),
        ado_item_id=1042,
        ado_item_url="https://dev.azure.com/org/project/_workitems/1042",
    )
    assert wi.item_type == WorkItemType.BUG
