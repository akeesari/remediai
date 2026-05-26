from __future__ import annotations

from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

_API_VERSION = "7.1"


class AzureDevOpsClient:
    """Async client for Azure DevOps Repos REST API.

    Authenticates with a Personal Access Token (PAT).
    Use ``from_settings(settings)`` to construct from app config.
    Call ``aclose()`` when done (or use as an async context manager).
    """

    def __init__(
        self,
        org_url: str,
        project: str,
        repository: str,
        pat: str,
        branch: str = "main",
    ) -> None:
        self.repository = repository
        self._branch = branch
        _base = f"{org_url.rstrip('/')}/{project}/_apis/git/repositories/{repository}"
        self._items_url = f"{_base}/items"
        self._commits_url = f"{_base}/commits"
        self._http = httpx.AsyncClient(
            auth=httpx.BasicAuth("", pat),
            timeout=30.0,
        )

    async def get_file_content(self, file_path: str) -> str | None:
        """Return raw text of *file_path* from the configured branch, or ``None`` if not found."""
        try:
            resp = await self._http.get(
                self._items_url,
                params={
                    "path": file_path,
                    "versionDescriptor.version": self._branch,
                    "versionDescriptor.versionType": "branch",
                    "$format": "text",
                    "api-version": _API_VERSION,
                },
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.text
        except httpx.HTTPStatusError as exc:
            logger.warning("ado_file_fetch_failed", path=file_path, status=exc.response.status_code)
            return None
        except httpx.RequestError as exc:
            logger.warning("ado_request_error", path=file_path, error=str(exc))
            return None

    async def get_latest_commit_sha(self) -> str:
        """Return the HEAD commit SHA on the configured branch, or empty string on failure."""
        try:
            resp = await self._http.get(
                self._commits_url,
                params={
                    "searchCriteria.itemVersion.version": self._branch,
                    "$top": 1,
                    "api-version": _API_VERSION,
                },
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            commits = data.get("value", [])
            return str(commits[0]["commitId"]) if commits else ""
        except (httpx.HTTPError, KeyError, IndexError) as exc:
            logger.warning("ado_commit_sha_failed", error=str(exc))
            return ""

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> AzureDevOpsClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    @classmethod
    def from_settings(cls, settings: Any) -> AzureDevOpsClient:
        pat_field = settings.azure_devops_pat
        pat = (
            pat_field.get_secret_value()
            if hasattr(pat_field, "get_secret_value")
            else str(pat_field)
        )
        return cls(
            org_url=settings.azure_devops_org_url,
            project=settings.azure_devops_project,
            repository=settings.azure_devops_repository,
            pat=pat,
            branch=settings.azure_devops_branch,
        )
