"""Integration tests for ServiceBusPublisher with a mock Azure Service Bus client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from packages.domain.models.events import IncidentEvent
from packages.integrations.service_bus.publisher import ServiceBusPublisher, _build_message


def _make_event(**kwargs: object) -> IncidentEvent:
    defaults = {
        "incident_id": uuid4(),
        "correlation_id": uuid4(),
        "source": "TestService",
        "exception_type": "System.NullReferenceException",
        "exception_message": "Object reference not set.",
        "fingerprint": "abc123",
        "priority": "high",
        "status": "new",
    }
    defaults.update(kwargs)
    return IncidentEvent(**defaults)  # type: ignore[arg-type]


class TestBuildMessage:
    def test_message_id_equals_incident_id(self) -> None:
        event = _make_event()
        msg = _build_message(event)
        assert msg.message_id == str(event.incident_id)

    def test_subject_is_incident_new(self) -> None:
        event = _make_event()
        msg = _build_message(event)
        assert msg.subject == "incident.new"

    def test_content_type_is_json(self) -> None:
        event = _make_event()
        msg = _build_message(event)
        assert msg.content_type == "application/json"

    def test_application_properties_contain_source_priority_fingerprint(self) -> None:
        event = _make_event(source="OrderSvc", priority="critical", fingerprint="fp42")
        msg = _build_message(event)
        props = msg.application_properties or {}
        assert props["source"] == "OrderSvc"
        assert props["priority"] == "critical"
        assert props["fingerprint"] == "fp42"

    def test_body_is_valid_incident_event_json(self) -> None:
        event = _make_event()
        msg = _build_message(event)
        body_bytes = b"".join(msg.body)  # body is an iterator of bytes
        recovered = IncidentEvent.model_validate_json(body_bytes)
        assert recovered.incident_id == event.incident_id


class TestServiceBusPublisher:
    def _patched_publisher(self) -> tuple[ServiceBusPublisher, MagicMock]:
        with patch("packages.integrations.service_bus.publisher.ServiceBusClient") as MockSBClient:
            mock_sb = MagicMock()
            MockSBClient.return_value = mock_sb

            from unittest.mock import MagicMock as MM

            from azure.identity import DefaultAzureCredential

            pub = ServiceBusPublisher(
                namespace="test-ns",
                topic="incident-events",
                credential=MM(spec=DefaultAzureCredential),
            )
            pub._client = mock_sb
            return pub, mock_sb

    @pytest.mark.asyncio
    async def test_publish_batch_sends_messages(self) -> None:
        events = [_make_event(), _make_event()]

        mock_sender = AsyncMock()
        mock_batch = MagicMock()
        mock_batch.add_message = MagicMock()
        mock_sender.create_message_batch = AsyncMock(return_value=mock_batch)
        mock_sender.send_messages = AsyncMock()
        mock_sender.__aenter__ = AsyncMock(return_value=mock_sender)
        mock_sender.__aexit__ = AsyncMock(return_value=None)

        with patch("packages.integrations.service_bus.publisher.ServiceBusClient"):
            from unittest.mock import MagicMock as MM

            from azure.identity import DefaultAzureCredential

            pub = ServiceBusPublisher(
                namespace="test-ns",
                topic="incident-events",
                credential=MM(spec=DefaultAzureCredential),
            )
            pub._client = MagicMock()
            pub._client.get_topic_sender = MagicMock(return_value=mock_sender)

            await pub.publish_batch(events)

        assert mock_batch.add_message.call_count == 2
        mock_sender.send_messages.assert_awaited_once_with(mock_batch)

    @pytest.mark.asyncio
    async def test_publish_batch_uses_connection_string(self) -> None:
        events = [_make_event()]

        mock_sender = AsyncMock()
        mock_batch = MagicMock()
        mock_batch.add_message = MagicMock()
        mock_sender.create_message_batch = AsyncMock(return_value=mock_batch)
        mock_sender.send_messages = AsyncMock()
        mock_sender.__aenter__ = AsyncMock(return_value=mock_sender)
        mock_sender.__aexit__ = AsyncMock(return_value=None)

        with patch("packages.integrations.service_bus.publisher.ServiceBusClient.from_connection_string") as mock_from_cs:
            mock_client = MagicMock()
            mock_from_cs.return_value = mock_client
            mock_client.get_topic_sender = MagicMock(return_value=mock_sender)

            pub = ServiceBusPublisher(
                namespace="test-ns",
                topic="incident-events",
                connection_string="Endpoint=sb://localhost:5672/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=localkey",
            )
            await pub.publish_batch(events)

        mock_from_cs.assert_called_once()
        assert mock_batch.add_message.call_count == 1
        mock_sender.send_messages.assert_awaited_once_with(mock_batch)

    @pytest.mark.asyncio
    async def test_publish_batch_empty_list_is_noop(self) -> None:
        with patch("packages.integrations.service_bus.publisher.ServiceBusClient"):
            from unittest.mock import MagicMock as MM

            from azure.identity import DefaultAzureCredential

            pub = ServiceBusPublisher(
                namespace="test-ns",
                topic="incident-events",
                credential=MM(spec=DefaultAzureCredential),
            )
            mock_client = MagicMock()
            pub._client = mock_client

            await pub.publish_batch([])

        mock_client.get_topic_sender.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_incident_delegates_to_batch(self) -> None:
        event = _make_event()

        with patch("packages.integrations.service_bus.publisher.ServiceBusClient"):
            from unittest.mock import AsyncMock as AM
            from unittest.mock import MagicMock as MM

            from azure.identity import DefaultAzureCredential

            pub = ServiceBusPublisher(
                namespace="test-ns",
                topic="incident-events",
                credential=MM(spec=DefaultAzureCredential),
            )
            pub.publish_batch = AM(return_value=None)  # type: ignore[method-assign]
            await pub.publish_incident(event)

        pub.publish_batch.assert_awaited_once_with([event])

    @pytest.mark.asyncio
    async def test_servicebus_error_propagates(self) -> None:
        from azure.servicebus.exceptions import ServiceBusError

        mock_sender = AsyncMock()
        mock_sender.create_message_batch = AsyncMock(
            side_effect=ServiceBusError("connection failed")
        )
        mock_sender.__aenter__ = AsyncMock(return_value=mock_sender)
        mock_sender.__aexit__ = AsyncMock(return_value=None)

        with patch("packages.integrations.service_bus.publisher.ServiceBusClient"):
            from unittest.mock import MagicMock as MM

            from azure.identity import DefaultAzureCredential

            pub = ServiceBusPublisher(
                namespace="test-ns",
                topic="incident-events",
                credential=MM(spec=DefaultAzureCredential),
            )
            pub._client = MagicMock()
            pub._client.get_topic_sender = MagicMock(return_value=mock_sender)

            with pytest.raises(ServiceBusError):
                await pub.publish_batch([_make_event()])
