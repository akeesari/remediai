"""Integration tests for IngestionScheduler with mocked connector and publisher."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.domain.models.events import IncidentEvent
from packages.domain.models.incident import Incident


def _make_incident(**kwargs: object) -> Incident:
    defaults = {
        "source": "TestService",
        "exception_type": "System.NullReferenceException",
        "exception_message": "Object reference not set.",
    }
    defaults.update(kwargs)  # type: ignore[arg-type]
    return Incident(**defaults)  # type: ignore[arg-type]


def _make_settings(**overrides: object) -> MagicMock:
    s = MagicMock()
    s.azure_monitor_workspace_id = "ws-id"
    s.azure_servicebus_namespace = "test-ns"
    s.azure_servicebus_topic = "incident-events"
    s.ingestion_lookback_minutes = 10
    s.ingestion_poll_interval_seconds = 60
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


class TestIngestionSchedulerRunOnce:
    @pytest.mark.asyncio
    async def test_new_incidents_are_published(self) -> None:
        from apps.worker.ingestion.scheduler import IngestionScheduler

        incident = _make_incident()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()

        mock_factory = MagicMock(return_value=mock_session)

        with (
            patch("apps.worker.ingestion.scheduler.AzureMonitorClient") as MockMonitor,
            patch("apps.worker.ingestion.scheduler.IngestionConnector") as MockConnector,
            patch("apps.worker.ingestion.scheduler.ServiceBusPublisher") as MockPublisher,
        ):
            mock_monitor_inst = AsyncMock()
            mock_monitor_inst.__aenter__ = AsyncMock(return_value=mock_monitor_inst)
            mock_monitor_inst.__aexit__ = AsyncMock(return_value=None)
            MockMonitor.return_value = mock_monitor_inst

            mock_connector_inst = AsyncMock()
            mock_connector_inst.run = AsyncMock(return_value=[incident])
            MockConnector.return_value = mock_connector_inst

            mock_publisher_inst = AsyncMock()
            mock_publisher_inst.__aenter__ = AsyncMock(return_value=mock_publisher_inst)
            mock_publisher_inst.__aexit__ = AsyncMock(return_value=None)
            mock_publisher_inst.publish_batch = AsyncMock()
            MockPublisher.return_value = mock_publisher_inst

            scheduler = IngestionScheduler(
                settings=_make_settings(),
                session_factory=mock_factory,
            )
            events = await scheduler.run_once()

        assert len(events) == 1
        assert isinstance(events[0], IncidentEvent)
        assert events[0].incident_id == incident.id
        mock_publisher_inst.publish_batch.assert_awaited_once()
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_new_incidents_skips_publish(self) -> None:
        from apps.worker.ingestion.scheduler import IngestionScheduler

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()

        mock_factory = MagicMock(return_value=mock_session)

        with (
            patch("apps.worker.ingestion.scheduler.AzureMonitorClient") as MockMonitor,
            patch("apps.worker.ingestion.scheduler.IngestionConnector") as MockConnector,
            patch("apps.worker.ingestion.scheduler.ServiceBusPublisher") as MockPublisher,
        ):
            mock_monitor_inst = AsyncMock()
            mock_monitor_inst.__aenter__ = AsyncMock(return_value=mock_monitor_inst)
            mock_monitor_inst.__aexit__ = AsyncMock(return_value=None)
            MockMonitor.return_value = mock_monitor_inst

            mock_connector_inst = AsyncMock()
            mock_connector_inst.run = AsyncMock(return_value=[])
            MockConnector.return_value = mock_connector_inst

            scheduler = IngestionScheduler(
                settings=_make_settings(),
                session_factory=mock_factory,
            )
            events = await scheduler.run_once()

        assert events == []
        MockPublisher.assert_not_called()
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_monitor_workspace_id_skips_ingestion(self) -> None:
        from apps.worker.ingestion.scheduler import IngestionScheduler

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()

        mock_factory = MagicMock(return_value=mock_session)
        scheduler = IngestionScheduler(
            settings=_make_settings(azure_monitor_workspace_id=""),
            session_factory=mock_factory,
        )
        events = await scheduler.run_once()

        assert events == []
        mock_session.commit.assert_not_awaited()
        mock_session.rollback.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_connector_error_rolls_back_session(self) -> None:
        from apps.worker.ingestion.scheduler import IngestionScheduler

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()

        mock_factory = MagicMock(return_value=mock_session)

        with (
            patch("apps.worker.ingestion.scheduler.AzureMonitorClient") as MockMonitor,
            patch("apps.worker.ingestion.scheduler.IngestionConnector") as MockConnector,
        ):
            mock_monitor_inst = AsyncMock()
            mock_monitor_inst.__aenter__ = AsyncMock(return_value=mock_monitor_inst)
            mock_monitor_inst.__aexit__ = AsyncMock(return_value=None)
            MockMonitor.return_value = mock_monitor_inst

            mock_connector_inst = AsyncMock()
            mock_connector_inst.run = AsyncMock(side_effect=RuntimeError("DB down"))
            MockConnector.return_value = mock_connector_inst

            scheduler = IngestionScheduler(
                settings=_make_settings(),
                session_factory=mock_factory,
            )

            with pytest.raises(RuntimeError, match="DB down"):
                await scheduler.run_once()

        mock_session.rollback.assert_awaited_once()
        mock_session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_event_fields_match_incident(self) -> None:
        from apps.worker.ingestion.scheduler import IngestionScheduler

        incident = _make_incident(
            source="PaymentService",
            exception_type="System.TimeoutException",
            exception_message="The operation timed out.",
        )

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()

        mock_factory = MagicMock(return_value=mock_session)

        with (
            patch("apps.worker.ingestion.scheduler.AzureMonitorClient") as MockMonitor,
            patch("apps.worker.ingestion.scheduler.IngestionConnector") as MockConnector,
            patch("apps.worker.ingestion.scheduler.ServiceBusPublisher") as MockPublisher,
        ):
            mock_monitor_inst = AsyncMock()
            mock_monitor_inst.__aenter__ = AsyncMock(return_value=mock_monitor_inst)
            mock_monitor_inst.__aexit__ = AsyncMock(return_value=None)
            MockMonitor.return_value = mock_monitor_inst

            mock_connector_inst = AsyncMock()
            mock_connector_inst.run = AsyncMock(return_value=[incident])
            MockConnector.return_value = mock_connector_inst

            mock_publisher_inst = AsyncMock()
            mock_publisher_inst.__aenter__ = AsyncMock(return_value=mock_publisher_inst)
            mock_publisher_inst.__aexit__ = AsyncMock(return_value=None)
            mock_publisher_inst.publish_batch = AsyncMock()
            MockPublisher.return_value = mock_publisher_inst

            scheduler = IngestionScheduler(
                settings=_make_settings(),
                session_factory=mock_factory,
            )
            events = await scheduler.run_once()

        event = events[0]
        assert event.incident_id == incident.id
        assert event.source == "PaymentService"
        assert event.exception_type == "System.TimeoutException"
        assert event.fingerprint == incident.fingerprint
        assert event.priority == "medium"
        assert event.status == "new"
