from __future__ import annotations

import base64
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

_API_VERSION = "7.1"


class ADOReposWriterError(RuntimeError):
    """Raised when an Azure DevOps Repos write operation fails."""


class ADOReposWriter:
    """Async client for writing to Azure DevOps Repos (branches, pushes, PRs).

    Authenticates with a Personal Access Token (PAT).
    Use ``from_settings(settings)`` to construct from app config.
    """

    def __init__(
        self,
        org_url: str,
        project: str,
        repository: str,
        pat: str,
        default_branch: str = "main",
    ) -> None:
        self.repository = repository
        self.default_branch = default_branch
        _base = f"{org_url.rstrip('/')}/{project}/_apis/git/repositories/{repository}"
        self._refs_url = f"{_base}/refs"
        self._pushes_url = f"{_base}/pushes"
        self._pr_url = f"{org_url.rstrip('/')}/{project}/_apis/git/pullrequests"
        self._http = httpx.AsyncClient(
            auth=httpx.BasicAuth("", pat),
            headers={"Content-Type": "application/json"},
            timeout=30.0,
        )

    async def create_branch(self, branch_name: str, from_sha: str) -> None:
        """Create a new Git ref (branch) from *from_sha*."""
        payload = [
            {
                "name": f"refs/heads/{branch_name}",
                "oldObjectId": "0000000000000000000000000000000000000000",
                "newObjectId": from_sha,
            }
        ]
        resp = await self._http.post(
            self._refs_url,
            params={"api-version": _API_VERSION},
            json=payload,
        )
        if resp.status_code >= 400:
            raise ADOReposWriterError(f"create_branch failed: {resp.status_code} {resp.text[:200]}")
        logger.info("ado_branch_created", branch=branch_name)

    async def get_latest_commit_sha(self) -> str:
        """Return the HEAD commit SHA of the default branch."""
        resp = await self._http.get(
            self._refs_url,
            params={
                "filter": f"heads/{self.default_branch}",
                "api-version": _API_VERSION,
            },
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        refs: list[dict[str, Any]] = data.get("value", [])
        if not refs:
            raise ADOReposWriterError(f"No ref found for branch '{self.default_branch}'")
        return str(refs[0]["objectId"])

    async def push_patch(
        self,
        branch: str,
        file_path: str,
        content: str,
        commit_message: str,
    ) -> None:
        """Push a file change to *branch* via the ADO Push API."""
        encoded = base64.b64encode(content.encode()).decode()
        payload = {
            "refUpdates": [{"name": f"refs/heads/{branch}", "oldObjectId": "0" * 40}],
            "commits": [
                {
                    "comment": commit_message,
                    "changes": [
                        {
                            "changeType": "edit",
                            "item": {"path": f"/{file_path.lstrip('/')}"},
                            "newContent": {"content": encoded, "contentType": "base64encoded"},
                        }
                    ],
                }
            ],
        }
        resp = await self._http.post(
            self._pushes_url,
            params={"api-version": _API_VERSION},
            json=payload,
        )
        if resp.status_code >= 400:
            raise ADOReposWriterError(f"push_patch failed: {resp.status_code} {resp.text[:200]}")
        logger.info("ado_patch_pushed", branch=branch, path=file_path)

    async def create_pull_request(
        self,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str,
        is_draft: bool = True,
    ) -> dict[str, Any]:
        """Create a pull request and return the ADO response dict.

        ``is_draft`` is always honoured — auto-complete is never set.
        """
        payload = {
            "title": title,
            "description": description,
            "sourceRefName": f"refs/heads/{source_branch}",
            "targetRefName": f"refs/heads/{target_branch}",
            "isDraft": is_draft,
        }
        resp = await self._http.post(
            self._pr_url,
            params={"api-version": _API_VERSION},
            json=payload,
        )
        if resp.status_code >= 400:
            raise ADOReposWriterError(
                f"create_pull_request failed: {resp.status_code} {resp.text[:200]}"
            )
        data: dict[str, Any] = resp.json()
        logger.info(
            "ado_pr_created",
            pr_id=data.get("pullRequestId"),
            branch=source_branch,
            is_draft=is_draft,
        )
        return data

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> ADOReposWriter:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    @classmethod
    def from_settings(cls, settings: Any) -> ADOReposWriter:
        return cls(
            org_url=getattr(settings, "azure_devops_org_url", ""),
            project=getattr(settings, "azure_devops_project", ""),
            repository=getattr(settings, "azure_devops_repository", ""),
            pat=getattr(settings, "azure_devops_pat", ""),
            default_branch=getattr(settings, "azure_devops_branch", "main"),
        )
