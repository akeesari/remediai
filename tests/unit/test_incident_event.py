"""Unit tests for the IncidentEvent domain model."""

from __future__ import annotations

from uuid import uuid4

from packages.domain.models.events import IncidentEvent
from packages.domain.models.incident import Incident, IncidentPriority, IncidentStatus


def _make_event(**kwargs: object) -> IncidentEvent:
    defaults = {
        "incident_id": uuid4(),
        "correlation_id": uuid4(),
        "source": "OrderService",
        "exception_type": "System.NullReferenceException",
        "exception_message": "Object reference not set.",
        "fingerprint": "abc123",
        "priority": IncidentPriority.HIGH.value,
        "status": IncidentStatus.NEW.value,
    }
    defaults.update(kwargs)
    return IncidentEvent(**defaults)  # type: ignore[arg-type]


class TestIncidentEvent:
    def test_default_published_at_is_utc(self) -> None:
        event = _make_event()
        assert event.published_at.tzinfo is not None

    def test_event_id_is_unique(self) -> None:
        e1 = _make_event()
        e2 = _make_event()
        assert e1.event_id != e2.event_id

    def test_json_round_trip(self) -> None:
        event = _make_event()
        json_str = event.model_dump_json()
        recovered = IncidentEvent.model_validate_json(json_str)
        assert recovered.incident_id == event.incident_id
        assert recovered.exception_type == event.exception_type
        assert recovered.fingerprint == event.fingerprint

    def test_all_fields_in_json(self) -> None:
        event = _make_event()
        json_str = event.model_dump_json()
        for field in (
            "incident_id",
            "correlation_id",
            "source",
            "exception_type",
            "exception_message",
            "fingerprint",
            "priority",
            "status",
            "published_at",
            "event_id",
        ):
            assert field in json_str

    def test_priority_stored_as_string(self) -> None:
        event = _make_event(priority="critical")
        assert event.priority == "critical"

    def test_status_stored_as_string(self) -> None:
        event = _make_event(status="new")
        assert event.status == "new"

    def test_from_incident(self) -> None:
        incident = Incident(
            source="PaymentService",
            exception_type="System.TimeoutException",
            exception_message="The operation timed out.",
        )
        event = IncidentEvent(
            incident_id=incident.id,
            correlation_id=incident.correlation_id,
            source=incident.source,
            exception_type=incident.exception_type,
            exception_message=incident.exception_message,
            fingerprint=incident.fingerprint,
            priority=incident.priority.value,
            status=incident.status.value,
        )
        assert event.incident_id == incident.id
        assert event.source == "PaymentService"
        assert event.priority == "medium"
        assert event.status == "new"
