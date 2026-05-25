"""Unit tests for /api/v1/targets endpoints."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest

from apps.api.core.config import get_settings
from apps.api.main import app
from packages.data_access.session import get_db_session

_NOW = datetime(2026, 5, 25, 10, 0, 0, tzinfo=UTC)


def _orm_target(
    *,
    environment: str = "local",
    target_type: str = "container",
    target_key: str = "api",
    display_name: str = "api",
    enabled: bool = True,
    metadata: dict[str, object] | None = None,
) -> MagicMock:
    target = MagicMock()
    target.id = uuid4()
    target.environment = environment
    target.target_type = target_type
    target.target_key = target_key
    target.display_name = display_name
    target.enabled = enabled
    target.metadata_json = metadata or {}
    target.created_at = _NOW
    target.updated_at = _NOW
    return target


def _scalars_result(items: list[object]) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    return result


def _make_session(*, execute_effects: list[MagicMock] | None = None) -> AsyncMock:
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=execute_effects or [])
    session.scalar = AsyncMock(return_value=None)
    session.add = MagicMock()
    return session


def _override(session: AsyncMock) -> None:
    async def _mock() -> AsyncGenerator[AsyncMock, None]:
        yield session

    app.dependency_overrides[get_db_session] = _mock


@pytest.fixture(autouse=True)
def clear_overrides() -> object:
    settings = get_settings()
    original_local_mode = settings.local_mode
    original_token = settings.target_api_token
    settings.local_mode = True
    settings.target_api_token = "local-dev-target-token"
    yield
    settings.local_mode = original_local_mode
    settings.target_api_token = original_token
    app.dependency_overrides.pop(get_db_session, None)


class TestListTargets:
    @pytest.mark.asyncio
    async def test_returns_targets_for_environment(self) -> None:
        session = _make_session(execute_effects=[_scalars_result([_orm_target()])])
        _override(session)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/targets?environment=local")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["environment"] == "local"
        assert body[0]["target_key"] == "api"


class TestUpsertTargets:
    @pytest.mark.asyncio
    async def test_upsert_creates_new_target(self) -> None:
        session = _make_session()
        _override(session)

        payload = {
            "environment": "local",
            "targets": [
                {
                    "target_type": "container",
                    "target_key": "api",
                    "display_name": "api",
                    "enabled": True,
                    "metadata": {},
                }
            ],
        }

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put("/api/v1/targets", json=payload)

        assert resp.status_code == 200
        assert resp.json()["updated"] == 1
        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_updates_existing_target(self) -> None:
        existing = _orm_target(enabled=False)
        session = _make_session()
        session.scalar = AsyncMock(return_value=existing)
        _override(session)

        payload = {
            "environment": "local",
            "targets": [
                {
                    "target_type": "container",
                    "target_key": "api",
                    "display_name": "API Service",
                    "enabled": True,
                    "metadata": {"team": "platform"},
                }
            ],
        }

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put("/api/v1/targets", json=payload)

        assert resp.status_code == 200
        assert resp.json()["updated"] == 1
        assert existing.display_name == "API Service"
        assert existing.enabled is True
        assert existing.metadata_json == {"team": "platform"}


class TestDiscoverTargets:
    @pytest.mark.asyncio
    async def test_discovered_local_targets_from_config(self) -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/targets/discovered?environment=local")

        assert resp.status_code == 200
        body = resp.json()
        assert any(item["target_key"] == "api" for item in body)

    @pytest.mark.asyncio
    async def test_discovered_kubernetes_defaults_to_empty(self) -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/targets/discovered?environment=kubernetes")

        assert resp.status_code == 200
        assert resp.json() == []


class TestTargetsAuthGuard:
    @pytest.mark.asyncio
    async def test_non_local_requires_valid_admin_token(self) -> None:
        settings = get_settings()
        settings.local_mode = False
        settings.target_api_token = "expected-token"

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            unauthorized = await client.get("/api/v1/targets/discovered?environment=local")
            authorized = await client.get(
                "/api/v1/targets/discovered?environment=local",
                headers={"X-Remediai-Admin-Token": "expected-token"},
            )

        assert unauthorized.status_code == 401
        assert authorized.status_code == 200
