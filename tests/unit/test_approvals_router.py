"""Unit tests for approval endpoints."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import httpx
import pytest

from apps.api.main import app
from packages.data_access.session import get_db_session

_NOW = datetime(2026, 5, 24, 10, 0, 0, tzinfo=UTC)


def _incident(*, id_: UUID | None = None, status: str = "analyzed") -> MagicMock:
    inc = MagicMock()
    inc.id = id_ or uuid4()
    inc.status = status
    inc.approval_status = None
    inc.approved_by = None
    inc.approved_at = None
    inc.approved_recommendation_rank = None
    return inc


def _analysis(recommendation_count: int = 2) -> MagicMock:
    analysis = MagicMock()
    analysis.created_at = _NOW
    analysis.recommendations = [
        {"rank": i + 1, "title": f"Rec {i + 1}"} for i in range(recommendation_count)
    ]
    analysis.agent_trace = []
    return analysis


def _result(value: object) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _session_with_results(results: list[MagicMock]) -> AsyncMock:
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=results)
    session.add = MagicMock()
    return session


def _override(session: AsyncMock) -> None:
    async def _mock() -> AsyncGenerator[AsyncMock, None]:
        yield session

    app.dependency_overrides[get_db_session] = _mock


@pytest.fixture(autouse=True)
def clear_overrides() -> object:
    yield
    app.dependency_overrides.pop(get_db_session, None)


class TestApproveEndpoint:
    @pytest.mark.asyncio
    async def test_approve_analyzed_incident(self) -> None:
        inc = _incident()
        analysis = _analysis(recommendation_count=2)

        session = _session_with_results([_result(inc), _result(analysis)])

        _override(session)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v1/incidents/{inc.id}/approve",
                json={"recommendation_rank": 1, "approved_by": "engineer@contoso.com"},
            )

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["approval_status"] == "approved"
        assert payload["approved_recommendation_rank"] == 1
        assert inc.approval_status == "approved"
        assert inc.approved_recommendation_rank == 1
        assert analysis.agent_trace[-1]["agent_name"] == "human_approval"
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_approve_non_analyzed_returns_409(self) -> None:
        inc = _incident(status="new")
        session = _session_with_results([_result(inc)])

        _override(session)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v1/incidents/{inc.id}/approve",
                json={"recommendation_rank": 1, "approved_by": "engineer@contoso.com"},
            )

        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_approve_invalid_rank_returns_422(self) -> None:
        inc = _incident()
        analysis = _analysis(recommendation_count=1)
        session = _session_with_results([_result(inc), _result(analysis)])

        _override(session)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v1/incidents/{inc.id}/approve",
                json={"recommendation_rank": 9, "approved_by": "engineer@contoso.com"},
            )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_approve_unknown_incident_returns_404(self) -> None:
        session = _session_with_results([_result(None)])

        _override(session)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v1/incidents/{uuid4()}/approve",
                json={"recommendation_rank": 1, "approved_by": "engineer@contoso.com"},
            )

        assert resp.status_code == 404


class TestRejectEndpoint:
    @pytest.mark.asyncio
    async def test_reject_incident(self) -> None:
        inc = _incident()
        analysis = _analysis(recommendation_count=1)
        session = _session_with_results([_result(inc), _result(analysis)])

        _override(session)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/v1/incidents/{inc.id}/reject",
                json={"rejected_by": "engineer@contoso.com", "reason": "Not acceptable"},
            )

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["approval_status"] == "rejected"
        assert inc.approval_status == "rejected"
        assert analysis.agent_trace[-1]["agent_name"] == "human_approval"

    @pytest.mark.asyncio
    async def test_re_approve_after_reject(self) -> None:
        inc = _incident()
        analysis = _analysis(recommendation_count=2)
        session = _session_with_results(
            [
                _result(inc),
                _result(analysis),
                _result(inc),
                _result(analysis),
            ]
        )

        _override(session)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            reject_resp = await client.post(
                f"/api/v1/incidents/{inc.id}/reject",
                json={"rejected_by": "engineer@contoso.com", "reason": "Initial reject"},
            )
            approve_resp = await client.post(
                f"/api/v1/incidents/{inc.id}/approve",
                json={"recommendation_rank": 2, "approved_by": "engineer@contoso.com"},
            )

        assert reject_resp.status_code == 200
        assert approve_resp.status_code == 200
        assert inc.approval_status == "approved"
        assert inc.approved_recommendation_rank == 2
        assert session.commit.await_count == 2
