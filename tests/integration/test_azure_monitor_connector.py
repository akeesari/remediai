"""Integration tests for IngestionConnector with mocked Azure Monitor and DB session."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.domain.models.incident import Incident, IncidentStatus
from packages.integrations.azure_monitor.client import AzureMonitorClient


def _make_incident(**kwargs: Any) -> Incident:
    defaults: dict[str, Any] = {
        "source": "TestService",
        "exception_type": "System.NullReferenceException",
        "exception_message": "Object reference not set to an instance of an object.",
    }
    defaults.update(kwargs)
    return Incident(**defaults)


# ---------------------------------------------------------------------------
# AzureMonitorClient tests (mock the underlying LogsQueryClient)
# ---------------------------------------------------------------------------


class TestAzureMonitorClientFetchRecentExceptions:
    @pytest.mark.asyncio
    async def test_returns_parsed_incidents_on_success(self) -> None:
        mock_incident = _make_incident()

        with patch("packages.integrations.azure_monitor.client.LogsQueryClient") as MockLogs:
            instance = AsyncMock()
            MockLogs.return_value = instance

            mock_table = MagicMock()
            mock_table.columns = []
            mock_table.rows = []

            # Use a real LogsQueryResult so isinstance() checks in the client pass.
            from azure.monitor.query import LogsQueryResult

            mock_result = LogsQueryResult(tables=[mock_table])
            instance.query_workspace = AsyncMock(return_value=mock_result)

            with patch(
                "packages.integrations.azure_monitor.client.parse_exception_rows",
                return_value=[mock_incident],
            ):
                from azure.identity import DefaultAzureCredential

                client = AzureMonitorClient(
                    workspace_id="test-workspace-id",
                    credential=MagicMock(spec=DefaultAzureCredential),
                )
                # Swap out internal client with our mock
                client._client = instance

                result = await client.fetch_recent_exceptions(lookback_minutes=5)

        assert len(result) == 1
        assert result[0].exception_type == "System.NullReferenceException"

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_tables(self) -> None:
        with patch("packages.integrations.azure_monitor.client.LogsQueryClient") as MockLogs:
            instance = AsyncMock()
            MockLogs.return_value = instance

            mock_result = MagicMock()
            mock_result.tables = []
            instance.query_workspace = AsyncMock(return_value=mock_result)

            from azure.identity import DefaultAzureCredential

            client = AzureMonitorClient(
                workspace_id="test-workspace-id",
                credential=MagicMock(spec=DefaultAzureCredential),
            )
            client._client = instance

            result = await client.fetch_recent_exceptions()

        assert result == []

    @pytest.mark.asyncio
    async def test_propagates_http_response_error(self) -> None:
        from azure.core.exceptions import HttpResponseError

        with patch("packages.integrations.azure_monitor.client.LogsQueryClient") as MockLogs:
            instance = AsyncMock()
            MockLogs.return_value = instance
            instance.query_workspace = AsyncMock(
                side_effect=HttpResponseError(message="Unauthorized", response=MagicMock())
            )

            from azure.identity import DefaultAzureCredential

            client = AzureMonitorClient(
                workspace_id="test-workspace-id",
                credential=MagicMock(spec=DefaultAzureCredential),
            )
            client._client = instance

            with pytest.raises(HttpResponseError):
                await client.fetch_recent_exceptions()

    @pytest.mark.asyncio
    async def test_context_manager_closes_client(self) -> None:
        from azure.identity import DefaultAzureCredential

        with patch("packages.integrations.azure_monitor.client.LogsQueryClient") as MockLogs:
            instance = AsyncMock()
            MockLogs.return_value = instance

            client = AzureMonitorClient(
                workspace_id="test-workspace-id",
                credential=MagicMock(spec=DefaultAzureCredential),
            )
            client._client = instance

            async with client:
                pass

            instance.close.assert_awaited_once()


# ---------------------------------------------------------------------------
# IngestionConnector tests
# ---------------------------------------------------------------------------


class TestIngestionConnector:
    @pytest.mark.asyncio
    async def test_new_incidents_are_persisted(self) -> None:
        from apps.worker.ingestion.connector import IngestionConnector

        incident = _make_incident()
        mock_client = AsyncMock(spec=AzureMonitorClient)
        mock_client.fetch_recent_exceptions = AsyncMock(return_value=[incident])

        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(return_value=None)  # not a duplicate
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        connector = IngestionConnector(session=mock_session, monitor_client=mock_client)
        result = await connector.run(lookback_minutes=10)

        assert len(result) == 1
        assert result[0].fingerprint == incident.fingerprint
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_duplicate_incidents_are_skipped(self) -> None:
        from apps.worker.ingestion.connector import IngestionConnector

        incident = _make_incident()
        mock_client = AsyncMock(spec=AzureMonitorClient)
        mock_client.fetch_recent_exceptions = AsyncMock(return_value=[incident])

        existing_orm = MagicMock()  # simulates a DB row already present
        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(return_value=existing_orm)
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        connector = IngestionConnector(session=mock_session, monitor_client=mock_client)
        result = await connector.run(lookback_minutes=10)

        assert result == []
        mock_session.add.assert_not_called()
        mock_session.flush.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_fetch_returns_empty_list(self) -> None:
        from apps.worker.ingestion.connector import IngestionConnector

        mock_client = AsyncMock(spec=AzureMonitorClient)
        mock_client.fetch_recent_exceptions = AsyncMock(return_value=[])

        mock_session = AsyncMock()

        connector = IngestionConnector(session=mock_session, monitor_client=mock_client)
        result = await connector.run()

        assert result == []
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_mixed_new_and_duplicate_incidents(self) -> None:
        from apps.worker.ingestion.connector import IngestionConnector

        new_incident = _make_incident(exception_type="System.NullReferenceException")
        dup_incident = _make_incident(exception_type="System.TimeoutException")

        mock_client = AsyncMock(spec=AzureMonitorClient)
        mock_client.fetch_recent_exceptions = AsyncMock(return_value=[new_incident, dup_incident])

        existing_orm = MagicMock()
        mock_session = AsyncMock()
        # first call: new_incident → None (new), second call: dup_incident → existing_orm (dup)
        mock_session.scalar = AsyncMock(side_effect=[None, existing_orm])
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        connector = IngestionConnector(session=mock_session, monitor_client=mock_client)
        result = await connector.run()

        assert len(result) == 1
        assert result[0].fingerprint == new_incident.fingerprint
        assert mock_session.add.call_count == 1

    @pytest.mark.asyncio
    async def test_incident_status_is_new(self) -> None:
        from apps.worker.ingestion.connector import IngestionConnector

        incident = _make_incident()
        mock_client = AsyncMock(spec=AzureMonitorClient)
        mock_client.fetch_recent_exceptions = AsyncMock(return_value=[incident])

        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(return_value=None)
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        connector = IngestionConnector(session=mock_session, monitor_client=mock_client)
        result = await connector.run()

        assert result[0].status == IncidentStatus.NEW
