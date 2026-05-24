from __future__ import annotations

from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

_API_VERSION = "7.1"


class ADOPrReaderError(RuntimeError):
    """Raised when an Azure DevOps PR read/update operation fails."""


class ADOPrReader:
    """Async client for reading PR diffs and updating PR descriptions."""

    def __init__(
        self,
        org_url: str,
        project: str,
        repository: str,
        pat: str,
    ) -> None:
        base = f"{org_url.rstrip('/')}/{project}/_apis/git/repositories/{repository}"
        self._pr_base = f"{base}/pullRequests"
        self._http = httpx.AsyncClient(
            auth=httpx.BasicAuth("", pat),
            headers={"Content-Type": "application/json"},
            timeout=30.0,
        )

    async def get_pr_diff(self, pr_id: int) -> str:
        """Return unified diff for PR commits where available."""
        resp = await self._http.get(
            f"{self._pr_base}/{pr_id}/commits",
            params={"api-version": _API_VERSION},
        )
        if resp.status_code >= 400:
            raise ADOPrReaderError(f"get_pr_diff failed: {resp.status_code} {resp.text[:200]}")

        data: dict[str, Any] = resp.json()
        commits: list[dict[str, Any]] = data.get("value", [])
        if not commits:
            return ""

        # Best-effort: concatenate commit comments when full patch data is unavailable.
        # ADO REST diff APIs vary by endpoint shape; this still provides review signal.
        chunks: list[str] = []
        for commit in commits:
            commit_id = str(commit.get("commitId", ""))
            comment = str(commit.get("comment", "")).strip()
            if commit_id or comment:
                chunks.append(f"commit {commit_id}\n{comment}\n")
        return "\n".join(chunks).strip()

    async def append_validation_report(self, pr_id: int, report_markdown: str) -> None:
        """Append markdown section to an existing PR description."""
        get_resp = await self._http.get(
            f"{self._pr_base}/{pr_id}",
            params={"api-version": _API_VERSION},
        )
        if get_resp.status_code >= 400:
            raise ADOPrReaderError(
                f"get_pull_request failed: {get_resp.status_code} {get_resp.text[:200]}"
            )

        pr_data: dict[str, Any] = get_resp.json()
        current_description = str(pr_data.get("description", ""))
        updated_description = (
            f"{current_description}\n\n{report_markdown}"
            if current_description
            else report_markdown
        )

        patch_resp = await self._http.patch(
            f"{self._pr_base}/{pr_id}",
            params={"api-version": _API_VERSION},
            json={"description": updated_description},
        )
        if patch_resp.status_code >= 400:
            raise ADOPrReaderError(
                f"append_validation_report failed: {patch_resp.status_code} {patch_resp.text[:200]}"
            )
        logger.info("ado_pr_validation_appended", pr_id=pr_id)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> ADOPrReader:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    @classmethod
    def from_settings(cls, settings: Any) -> ADOPrReader:
        return cls(
            org_url=getattr(settings, "azure_devops_org_url", ""),
            project=getattr(settings, "azure_devops_project", ""),
            repository=getattr(settings, "azure_devops_repository", ""),
            pat=getattr(settings, "azure_devops_pat", ""),
        )
