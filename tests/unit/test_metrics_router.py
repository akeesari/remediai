"""Unit tests for GET /api/v1/metrics — DB session is mocked throughout."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from apps.api.main import app
from packages.data_access.session import get_db_session


def _rows_result(rows: list[tuple[object, ...]]) -> MagicMock:
    r = MagicMock()
    r.scalar_one.return_value = rows[0][0] if rows else 0
    r.all.return_value = rows
    return r


def _scalar_result(value: int) -> MagicMock:
    r = MagicMock()
    r.scalar_one.return_value = value
    return r


def _agg_result(rows: list[tuple[object, ...]]) -> MagicMock:
    r = MagicMock()
    r.all.return_value = rows
    return r


def _make_session(execute_side_effects: list[MagicMock]) -> AsyncMock:
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=execute_side_effects)
    return session


def _override(session: AsyncMock) -> None:
    async def _mock() -> AsyncGenerator[AsyncMock, None]:
        yield session

    app.dependency_overrides[get_db_session] = _mock


def _clear() -> None:
    app.dependency_overrides.pop(get_db_session, None)


@pytest.fixture(autouse=True)
def clear_overrides() -> object:
    yield
    _clear()


def _default_session(
    total: int = 5,
    analyzed: int = 3,
    by_status: list[tuple[str, int]] | None = None,
    by_priority: list[tuple[str, int]] | None = None,
    top_errors: list[tuple[str, int]] | None = None,
) -> AsyncMock:
    if by_status is None:
        by_status = [("analyzed", 3), ("new", 2)]
    if by_priority is None:
        by_priority = [("high", 3), ("medium", 2)]
    if top_errors is None:
        top_errors = [("System.NullReferenceException", 4), ("System.TimeoutException", 1)]
    return _make_session(
        [
            _scalar_result(total),
            _scalar_result(analyzed),
            _agg_result(by_status),
            _agg_result(by_priority),
            _agg_result(top_errors),
        ]
    )


class TestGetMetrics:
    @pytest.mark.asyncio
    async def test_returns_200(self) -> None:
        _override(_default_session())
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/metrics")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_total_incidents_correct(self) -> None:
        _override(_default_session(total=10))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/metrics")
        assert resp.json()["total_incidents"] == 10

    @pytest.mark.asyncio
    async def test_total_analyzed_correct(self) -> None:
        _override(_default_session(total=10, analyzed=7))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/metrics")
        assert resp.json()["total_analyzed"] == 7

    @pytest.mark.asyncio
    async def test_by_status_structure(self) -> None:
        _override(_default_session(by_status=[("analyzed", 5), ("new", 3)]))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/metrics")
        by_status = resp.json()["by_status"]
        assert len(by_status) == 2
        assert any(s["status"] == "analyzed" and s["count"] == 5 for s in by_status)

    @pytest.mark.asyncio
    async def test_by_priority_structure(self) -> None:
        _override(_default_session(by_priority=[("critical", 2), ("high", 3)]))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/metrics")
        by_priority = resp.json()["by_priority"]
        assert any(p["priority"] == "critical" and p["count"] == 2 for p in by_priority)

    @pytest.mark.asyncio
    async def test_top_errors_structure(self) -> None:
        _override(_default_session(top_errors=[("System.NullReferenceException", 8)]))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/metrics")
        top = resp.json()["top_errors"]
        assert len(top) == 1
        assert top[0]["exception_type"] == "System.NullReferenceException"
        assert top[0]["count"] == 8

    @pytest.mark.asyncio
    async def test_empty_database_returns_zeros(self) -> None:
        _override(
            _default_session(total=0, analyzed=0, by_status=[], by_priority=[], top_errors=[])
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/metrics")
        body = resp.json()
        assert body["total_incidents"] == 0
        assert body["by_status"] == []
        assert body["top_errors"] == []

    @pytest.mark.asyncio
    async def test_response_has_all_required_fields(self) -> None:
        _override(_default_session())
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/metrics")
        body = resp.json()
        assert "total_incidents" in body
        assert "total_analyzed" in body
        assert "by_status" in body
        assert "by_priority" in body
        assert "top_errors" in body
