from __future__ import annotations

from datetime import timedelta
from typing import Any, cast

import structlog
from azure.core.credentials_async import AsyncTokenCredential
from azure.core.exceptions import HttpResponseError
from azure.identity import DefaultAzureCredential
from azure.monitor.query import LogsQueryPartialResult, LogsQueryResult
from azure.monitor.query.aio import LogsQueryClient

from packages.domain.models.incident import Incident
from packages.integrations.azure_monitor.kql_queries import exceptions_kql
from packages.integrations.azure_monitor.parser import parse_exception_rows

logger = structlog.get_logger()


class AzureMonitorClient:
    """Async client for querying Application Insights exceptions via KQL."""

    def __init__(
        self,
        workspace_id: str,
        credential: AsyncTokenCredential | None = None,
    ) -> None:
        self._workspace_id = workspace_id
        # DefaultAzureCredential satisfies AsyncTokenCredential at runtime;
        # cast resolves mypy's structural-subtyping limitation with azure-identity stubs.
        self._credential: AsyncTokenCredential = credential or cast(
            AsyncTokenCredential, DefaultAzureCredential()
        )
        self._client = LogsQueryClient(self._credential)

    async def fetch_recent_exceptions(self, lookback_minutes: int = 10) -> list[Incident]:
        """Query Application Insights for exceptions in the last *lookback_minutes* minutes."""
        query = exceptions_kql(lookback_minutes=lookback_minutes)
        timespan = timedelta(minutes=lookback_minutes + 1)

        log = logger.bind(workspace_id=self._workspace_id, lookback_minutes=lookback_minutes)
        log.info("azure_monitor_query_start")

        try:
            result = await self._client.query_workspace(
                workspace_id=self._workspace_id,
                query=query,
                timespan=timespan,
            )
        except HttpResponseError as exc:
            log.error("azure_monitor_query_failed", error=str(exc), status_code=exc.status_code)
            raise

        if isinstance(result, LogsQueryPartialResult):
            log.warning("azure_monitor_partial_result", error=str(result.partial_error))
            tables = result.partial_data
        elif isinstance(result, LogsQueryResult):
            tables = result.tables
        else:
            return []

        if not tables:
            log.info("azure_monitor_no_tables_returned")
            return []

        incidents = parse_exception_rows(tables[0])
        log.info("azure_monitor_query_complete", row_count=len(incidents))
        return incidents

    async def close(self) -> None:
        await self._client.close()

    async def __aenter__(self) -> AzureMonitorClient:
        return self

    async def __aexit__(self, *_args: Any) -> None:
        await self.close()
