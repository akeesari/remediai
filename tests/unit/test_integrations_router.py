"""Unit tests for GET /api/v1/integrations/health."""

from __future__ import annotations

import httpx
import pytest

from apps.api.main import app


class TestIntegrationsHealth:
    @pytest.mark.asyncio
    async def test_returns_200(self) -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/integrations/health")

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_response_contains_provider_status_and_warnings(self) -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/integrations/health")

        body = resp.json()
        assert "llm_provider_id" in body
        assert "retrieval_provider_id" in body
        assert "scm" in body
        assert "ticketing" in body
        assert "warnings" in body
        assert "provider_id" in body["scm"]
        assert "configured" in body["scm"]
        assert isinstance(body["warnings"], list)
