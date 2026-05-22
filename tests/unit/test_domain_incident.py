import hashlib
from uuid import UUID

import pytest

from packages.domain import Incident, IncidentPriority, IncidentStatus


def test_incident_defaults() -> None:
    inc = Incident(source="api", exception_type="NullReferenceException", exception_message="Object not set")
    assert isinstance(inc.id, UUID)
    assert isinstance(inc.correlation_id, UUID)
    assert inc.priority == IncidentPriority.MEDIUM
    assert inc.status == IncidentStatus.NEW
    assert inc.stack_trace is None
    assert inc.raw_payload == {}


def test_incident_fingerprint_derived_automatically() -> None:
    inc = Incident(source="api", exception_type="TimeoutException", exception_message="Connection timed out")
    expected = hashlib.sha256(b"TimeoutException:Connection timed out").hexdigest()
    assert inc.fingerprint == expected


def test_incident_fingerprint_truncates_long_message() -> None:
    long_msg = "x" * 500
    inc = Incident(source="api", exception_type="Error", exception_message=long_msg)
    expected = hashlib.sha256(f"Error:{'x' * 200}".encode()).hexdigest()
    assert inc.fingerprint == expected


def test_incident_fingerprint_not_overwritten_if_supplied() -> None:
    inc = Incident(
        source="api",
        exception_type="Error",
        exception_message="msg",
        fingerprint="custom-fingerprint",
    )
    assert inc.fingerprint == "custom-fingerprint"


def test_incident_status_transitions() -> None:
    inc = Incident(source="api", exception_type="Error", exception_message="msg")
    inc.status = IncidentStatus.TRIAGING
    assert inc.status == IncidentStatus.TRIAGING


@pytest.mark.parametrize("priority", list(IncidentPriority))
def test_incident_all_priorities(priority: IncidentPriority) -> None:
    inc = Incident(source="api", exception_type="E", exception_message="m", priority=priority)
    assert inc.priority == priority


def test_incident_serialises_to_dict() -> None:
    inc = Incident(source="api", exception_type="NullReferenceException", exception_message="msg")
    data = inc.model_dump()
    assert data["exception_type"] == "NullReferenceException"
    assert "fingerprint" in data
    assert "created_at" in data
