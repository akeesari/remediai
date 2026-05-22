from packages.domain import IncidentState
from packages.domain.exceptions import (
    DomainError,
    DuplicateIncidentError,
    IncidentNotFoundError,
)


def test_incident_state_is_typed_dict() -> None:
    state: IncidentState = {
        "incident_id": "abc-123",
        "correlation_id": "corr-456",
        "exception_type": "NullReferenceException",
        "exception_message": "Object reference not set",
        "stack_trace": "at UserService.GetById line 42",
        "raw_payload": {},
        "priority": None,
        "triage_labels": [],
        "group_id": None,
        "root_cause_summary": None,
        "root_cause_json": None,
        "code_snippets": [],
        "rag_results": [],
        "recommendations": [],
        "ado_bug_id": None,
        "ado_bug_url": None,
        "pr_branch": None,
        "pr_url": None,
        "validation_report": None,
        "agent_trace": [],
        "errors": [],
    }
    assert state["incident_id"] == "abc-123"
    assert state["triage_labels"] == []


def test_incident_state_partial_construction() -> None:
    # LangGraph builds state incrementally — partial dicts are valid
    state: IncidentState = {"incident_id": "x", "errors": []}
    assert state["incident_id"] == "x"


def test_incident_state_accumulates_errors() -> None:
    state: IncidentState = {"errors": []}
    state["errors"].append("triage_agent: LLM timeout")
    assert len(state["errors"]) == 1


def test_domain_error_hierarchy() -> None:
    assert issubclass(IncidentNotFoundError, DomainError)
    assert issubclass(DuplicateIncidentError, DomainError)


def test_incident_not_found_error_raises() -> None:
    with pytest.raises(IncidentNotFoundError):
        raise IncidentNotFoundError("incident-id-xyz not found")


def test_duplicate_incident_error_raises() -> None:
    with pytest.raises(DuplicateIncidentError):
        raise DuplicateIncidentError("fingerprint already exists")


import pytest  # noqa: E402
