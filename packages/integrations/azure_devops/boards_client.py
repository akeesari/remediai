from __future__ import annotations

from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

_API_VERSION = "7.1"

_ADO_PRIORITY: dict[str, int] = {
    "critical": 1,
    "high": 2,
    "medium": 3,
    "low": 4,
}


class AzureDevOpsBoardsClient:
    """Async client for Azure DevOps Boards work-item REST API.

    Creates Bug work items from incident analysis.
    Use ``from_settings(settings)`` to construct from app config.
    Call ``aclose()`` when done (or use as an async context manager).
    """

    def __init__(self, org_url: str, project: str, pat: str) -> None:
        _base = f"{org_url.rstrip('/')}/{project}/_apis/wit/workitems"
        self._bug_url = f"{_base}/$Bug"
        self._wi_url = f"{org_url.rstrip('/')}/{project}/_workitems/edit"
        self._http = httpx.AsyncClient(
            auth=httpx.BasicAuth("", pat),
            headers={"Content-Type": "application/json-patch+json"},
            timeout=30.0,
        )

    async def create_bug(
        self,
        title: str,
        description: str,
        priority: str = "medium",
        tags: str = "",
    ) -> dict[str, Any]:
        """Create a Bug work item and return the raw ADO response dict.

        Response contains at minimum ``id`` (int) and
        ``_links.html.href`` (str) for the web URL.
        """
        ado_priority = _ADO_PRIORITY.get(priority.lower(), 3)
        patch: list[dict[str, Any]] = [
            {"op": "add", "path": "/fields/System.Title", "value": title},
            {"op": "add", "path": "/fields/System.Description", "value": description},
            {"op": "add", "path": "/fields/Microsoft.VSTS.Common.Priority", "value": ado_priority},
        ]
        if tags:
            patch.append({"op": "add", "path": "/fields/System.Tags", "value": tags})

        resp = await self._http.post(
            self._bug_url,
            params={"api-version": _API_VERSION},
            json=patch,
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> AzureDevOpsBoardsClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    @classmethod
    def from_settings(cls, settings: Any) -> AzureDevOpsBoardsClient:
        return cls(
            org_url=settings.azure_devops_org_url,
            project=settings.azure_devops_project,
            pat=settings.azure_devops_pat,
        )
