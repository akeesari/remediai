"""Unit tests for Azure DevOps repos writer."""

from __future__ import annotations

import base64
from typing import Any

import httpx
import pytest

from packages.integrations.azure_devops.repos_writer import ADOReposWriter


async def _writer_with_handler(handler: Any) -> ADOReposWriter:
    writer = ADOReposWriter(
        org_url="https://dev.azure.com/org",
        project="proj",
        repository="repo",
        pat="pat",
    )
    await writer._http.aclose()
    writer._http = httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=30.0)
    return writer


@pytest.mark.asyncio
async def test_create_branch_calls_correct_endpoint() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith("/_apis/git/repositories/repo/refs")
        payload = await request.aread()
        assert b"refs/heads/remedia/abc/1" in payload
        return httpx.Response(200, json={"value": []})

    writer = await _writer_with_handler(handler)
    try:
        await writer.create_branch("remedia/abc/1", "a" * 40)
    finally:
        await writer.aclose()


@pytest.mark.asyncio
async def test_push_patch_calls_push_api() -> None:
    expected_content = "public class Demo {}"

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith("/_apis/git/repositories/repo/pushes")
        body = request.read().decode("utf-8")
        assert "refs/heads/remedia/abc/1" in body
        assert base64.b64encode(expected_content.encode()).decode() in body
        return httpx.Response(200, json={"pushId": 1})

    writer = await _writer_with_handler(handler)
    try:
        await writer.push_patch(
            branch="remedia/abc/1",
            file_path="src/Demo.cs",
            content=expected_content,
            commit_message="apply patch",
        )
    finally:
        await writer.aclose()


@pytest.mark.asyncio
async def test_create_pull_request_draft() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith("/proj/_apis/git/pullrequests")
        body = request.read().decode("utf-8")
        assert '"isDraft": true' in body
        return httpx.Response(200, json={"pullRequestId": 42, "url": "https://example/pr/42"})

    writer = await _writer_with_handler(handler)
    try:
        response = await writer.create_pull_request(
            source_branch="remedia/abc/1",
            target_branch="main",
            title="Title",
            description="Body",
            is_draft=True,
        )
    finally:
        await writer.aclose()

    assert response["pullRequestId"] == 42
