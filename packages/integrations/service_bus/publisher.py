from __future__ import annotations

from typing import Any

import structlog
from azure.core.credentials_async import AsyncTokenCredential
from azure.core.exceptions import HttpResponseError
from azure.identity import DefaultAzureCredential
from azure.servicebus import ServiceBusMessage
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus.exceptions import ServiceBusError

from packages.domain.models.events import IncidentEvent

logger = structlog.get_logger()

_SUBJECT = "incident.new"


class ServiceBusPublisher:
    """Publishes IncidentEvent messages to an Azure Service Bus topic."""

    def __init__(
        self,
        namespace: str,
        topic: str,
        connection_string: str = "",
        credential: AsyncTokenCredential | None = None,
    ) -> None:
        from typing import cast

        self._topic = topic
        if connection_string:
            self._client = ServiceBusClient.from_connection_string(connection_string)
        else:
            fqdn = f"{namespace}.servicebus.windows.net"
            _cred: AsyncTokenCredential = credential or cast(
                AsyncTokenCredential, DefaultAzureCredential()
            )
            self._client = ServiceBusClient(fully_qualified_namespace=fqdn, credential=_cred)

    async def publish_incident(self, event: IncidentEvent) -> None:
        """Send a single IncidentEvent as a Service Bus message."""
        await self.publish_batch([event])

    async def publish_batch(self, events: list[IncidentEvent]) -> None:
        """Send a batch of IncidentEvents in a single Service Bus transmission."""
        if not events:
            return

        log = logger.bind(topic=self._topic, count=len(events))

        try:
            async with self._client.get_topic_sender(topic_name=self._topic) as sender:
                batch = await sender.create_message_batch()
                for event in events:
                    msg = _build_message(event)
                    batch.add_message(msg)
                await sender.send_messages(batch)
        except (ServiceBusError, HttpResponseError) as exc:
            log.error("servicebus_publish_failed", error=str(exc))
            raise

        log.info("servicebus_publish_success")

    async def close(self) -> None:
        await self._client.close()

    async def __aenter__(self) -> ServiceBusPublisher:
        return self

    async def __aexit__(self, *_args: Any) -> None:
        await self.close()


def _build_message(event: IncidentEvent) -> ServiceBusMessage:
    return ServiceBusMessage(
        body=event.model_dump_json(),
        message_id=str(event.incident_id),
        subject=_SUBJECT,
        application_properties={
            "source": event.source,
            "priority": event.priority,
            "fingerprint": event.fingerprint,
        },
        content_type="application/json",
    )
