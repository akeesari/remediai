"""Unit tests for GET /api/v1/incidents — DB session is mocked throughout."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import httpx
import pytest

from apps.api.main import app
from packages.data_access.session import get_db_session

_NOW = datetime(2026, 5, 23, 12, 0, 0, tzinfo=UTC)


def _orm_incident(
    id_: UUID | None = None,
    exception_type: str = "System.NullReferenceException",
    exception_message: str = "Object reference not set.",
    priority: str = "high",
    status: str = "analyzed",
    work_items: list[object] | None = None,
) -> MagicMock:
    inc = MagicMock()
    inc.id = id_ or uuid4()
    inc.exception_type = exception_type
    inc.exception_message = exception_message
    inc.priority = priority
    inc.status = status
    inc.created_at = _NOW
    inc.updated_at = _NOW
    inc.stack_trace = None
    inc.approval_status = None
    inc.approved_by = None
    inc.approved_at = None
    inc.approved_recommendation_rank = None
    inc.work_items = work_items or []
    inc.analyses = []
    return inc


def _make_session(execute_side_effects: list[MagicMock]) -> AsyncMock:
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=execute_side_effects)
    return session


def _scalar_result(value: object) -> MagicMock:
    r = MagicMock()
    r.scalar_one.return_value = value
    r.scalar_one_or_none.return_value = value
    return r


def _scalars_result(items: list[object]) -> MagicMock:
    r = MagicMock()
    r.scalars.return_value.all.return_value = items
    return r


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


class TestListIncidents:
    @pytest.mark.asyncio
    async def test_returns_200_empty_list(self) -> None:
        _override(
            _make_session(
                [
                    _scalar_result(0),  # count
                    _scalars_result([]),  # items
                ]
            )
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/incidents")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []

    @pytest.mark.asyncio
    async def test_returns_incident_list(self) -> None:
        inc = _orm_incident()
        _override(
            _make_session(
                [
                    _scalar_result(1),  # count
                    _scalars_result([inc]),  # items
                    _scalars_result([inc.id]),  # analyzed_ids
                ]
            )
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/incidents")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1
        assert body["items"][0]["exception_type"] == "System.NullReferenceException"

    @pytest.mark.asyncio
    async def test_pagination_fields_present(self) -> None:
        _override(
            _make_session(
                [
                    _scalar_result(0),
                    _scalars_result([]),
                ]
            )
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/incidents?page=2&page_size=10")
        assert resp.status_code == 200
        body = resp.json()
        assert body["page"] == 2
        assert body["page_size"] == 10
        assert "pages" in body

    @pytest.mark.asyncio
    async def test_has_analysis_true_when_analyzed(self) -> None:
        inc = _orm_incident()
        _override(
            _make_session(
                [
                    _scalar_result(1),
                    _scalars_result([inc]),
                    _scalars_result([inc.id]),
                ]
            )
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/incidents")
        assert resp.json()["items"][0]["has_analysis"] is True

    @pytest.mark.asyncio
    async def test_has_analysis_false_when_not_analyzed(self) -> None:
        inc = _orm_incident()
        _override(
            _make_session(
                [
                    _scalar_result(1),
                    _scalars_result([inc]),
                    _scalars_result([]),  # no matching analysis IDs
                ]
            )
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/incidents")
        assert resp.json()["items"][0]["has_analysis"] is False

    @pytest.mark.asyncio
    async def test_ado_bug_url_from_work_item(self) -> None:
        wi = MagicMock()
        wi.ado_item_url = "https://dev.azure.com/org/proj/_workitems/edit/42"
        inc = _orm_incident(work_items=[wi])
        _override(
            _make_session(
                [
                    _scalar_result(1),
                    _scalars_result([inc]),
                    _scalars_result([]),
                ]
            )
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/incidents")
        assert "dev.azure.com" in resp.json()["items"][0]["ado_bug_url"]

    @pytest.mark.asyncio
    async def test_page_size_capped_at_100(self) -> None:
        _override(
            _make_session(
                [
                    _scalar_result(0),
                    _scalars_result([]),
                ]
            )
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/incidents?page_size=200")
        assert resp.status_code == 422  # validation error


class TestGetIncident:
    @pytest.mark.asyncio
    async def test_returns_200_with_detail(self) -> None:
        inc_id = uuid4()
        inc = _orm_incident(id_=inc_id)
        result = _scalar_result(inc)
        result.scalar_one_or_none.return_value = inc
        _override(_make_session([result]))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"/api/v1/incidents/{inc_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(inc_id)
        assert body["exception_type"] == "System.NullReferenceException"

    @pytest.mark.asyncio
    async def test_returns_404_for_unknown_id(self) -> None:
        result = _scalar_result(None)
        result.scalar_one_or_none.return_value = None
        _override(_make_session([result]))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"/api/v1/incidents/{uuid4()}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_detail_includes_analysis_fields(self) -> None:
        inc_id = uuid4()
        inc = _orm_incident(id_=inc_id)
        analysis = MagicMock()
        analysis.root_cause = "Null reference in service layer."
        analysis.root_cause_json = {"component": "UserService", "confidence": 0.8}
        analysis.recommendations = [{"rank": 1, "title": "Add null guard"}]
        analysis.code_snippets = []
        analysis.rag_results = []
        analysis.agent_trace = []
        inc.analyses = [analysis]
        result = _scalar_result(inc)
        result.scalar_one_or_none.return_value = inc
        _override(_make_session([result]))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"/api/v1/incidents/{inc_id}")
        body = resp.json()
        assert body["root_cause"] == "Null reference in service layer."
        assert body["root_cause_json"]["component"] == "UserService"
        assert len(body["recommendations"]) == 1

    @pytest.mark.asyncio
    async def test_detail_work_items_included(self) -> None:
        inc_id = uuid4()
        wi = MagicMock()
        wi.ado_item_id = 42
        wi.ado_item_url = "https://dev.azure.com/org/proj/_workitems/edit/42"
        wi.item_type = "bug"
        wi.pr_url = None
        inc = _orm_incident(id_=inc_id, work_items=[wi])
        result = _scalar_result(inc)
        result.scalar_one_or_none.return_value = inc
        _override(_make_session([result]))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"/api/v1/incidents/{inc_id}")
        work_items = resp.json()["work_items"]
        assert len(work_items) == 1
        assert work_items[0]["ado_item_id"] == 42

    @pytest.mark.asyncio
    async def test_detail_includes_approval_and_pr_fields(self) -> None:
        inc_id = uuid4()
        wi = MagicMock()
        wi.ado_item_id = 42
        wi.ado_item_url = "https://dev.azure.com/org/proj/_workitems/edit/42"
        wi.item_type = "bug"
        wi.pr_url = "https://dev.azure.com/org/proj/_git/repo/pullrequest/7"
        inc = _orm_incident(id_=inc_id, work_items=[wi])
        inc.approval_status = "approved"
        inc.approved_by = "engineer@contoso.com"
        inc.approved_at = _NOW
        inc.approved_recommendation_rank = 1

        result = _scalar_result(inc)
        result.scalar_one_or_none.return_value = inc
        _override(_make_session([result]))

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"/api/v1/incidents/{inc_id}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["approval_status"] == "approved"
        assert body["approved_by"] == "engineer@contoso.com"
        assert body["approved_recommendation_rank"] == 1
        assert body["pr_url"] == wi.pr_url

    @pytest.mark.asyncio
    async def test_detail_no_analysis_returns_empty_fields(self) -> None:
        inc_id = uuid4()
        inc = _orm_incident(id_=inc_id)
        inc.analyses = []
        result = _scalar_result(inc)
        result.scalar_one_or_none.return_value = inc
        _override(_make_session([result]))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"/api/v1/incidents/{inc_id}")
        body = resp.json()
        assert body["root_cause"] is None
        assert body["recommendations"] == []
