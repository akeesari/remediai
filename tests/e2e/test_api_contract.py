"""HTTP-level API contract tests against the real FastAPI app + real DB.

Seed data is inserted via db_session; the API client uses the same session
(overriding the FastAPI dependency) so seeded rows are visible to the router.
All changes are rolled back after each test.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from packages.data_access.models.analysis_orm import AnalysisOrm
from packages.data_access.models.incident_orm import IncidentOrm

from .conftest import make_incident_orm

pytestmark = pytest.mark.e2e


async def _seed_incidents(session: AsyncSession, count: int = 3) -> list[IncidentOrm]:
    incidents = []
    priorities = ["critical", "high", "medium"]
    statuses = ["new", "analyzed", "new"]
    for i in range(count):
        inc = make_incident_orm(priority=priorities[i], status=statuses[i])
        session.add(inc)
        incidents.append(inc)
    await session.flush()
    return incidents


async def _seed_analysis(session: AsyncSession, incident: IncidentOrm) -> AnalysisOrm:
    analysis = AnalysisOrm(
        id=uuid.uuid4(),
        incident_id=incident.id,
        root_cause="Null reference in UserService.",
        root_cause_json={"component": "UserService", "confidence": 0.85},
        recommendations=[{"rank": 1, "title": "Add null guard", "confidence": 0.85}],
        code_snippets=[],
        rag_results=[],
        agent_trace=[{"agent_name": "triage"}, {"agent_name": "root_cause"}],
        created_at=datetime.now(UTC),
    )
    session.add(analysis)
    await session.flush()
    return analysis


class TestIncidentListEndpoint:
    @pytest.mark.asyncio
    async def test_list_incidents_returns_paginated_shape(
        self, api_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        await _seed_incidents(db_session, count=3)

        resp = await api_client.get("/api/v1/incidents")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "pages" in data
        assert data["total"] >= 3

    @pytest.mark.asyncio
    async def test_list_incidents_filter_by_priority(
        self, api_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        await _seed_incidents(db_session, count=3)

        resp = await api_client.get("/api/v1/incidents", params={"priority": "critical"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(i["priority"] == "critical" for i in data["items"])

    @pytest.mark.asyncio
    async def test_list_incidents_filter_by_status(
        self, api_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        await _seed_incidents(db_session, count=3)

        resp = await api_client.get("/api/v1/incidents", params={"status": "analyzed"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(i["status"] == "analyzed" for i in data["items"])

    @pytest.mark.asyncio
    async def test_list_incidents_empty_db_returns_zero(self, api_client: AsyncClient) -> None:
        resp = await api_client.get("/api/v1/incidents")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


class TestIncidentDetailEndpoint:
    @pytest.mark.asyncio
    async def test_get_incident_detail_returns_full_shape(
        self, api_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        incidents = await _seed_incidents(db_session, count=1)
        incident = incidents[0]
        await _seed_analysis(db_session, incident)

        resp = await api_client.get(f"/api/v1/incidents/{incident.id}")
        assert resp.status_code == 200
        data = resp.json()

        assert data["id"] == str(incident.id)
        assert data["exception_type"] == incident.exception_type
        assert data["root_cause"] == "Null reference in UserService."
        assert isinstance(data["recommendations"], list)
        assert isinstance(data["agent_trace"], list)
        assert isinstance(data["work_items"], list)

    @pytest.mark.asyncio
    async def test_get_incident_404_on_missing(self, api_client: AsyncClient) -> None:
        resp = await api_client.get(f"/api/v1/incidents/{uuid.uuid4()}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_incident_no_analysis_returns_empty_fields(
        self, api_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        incidents = await _seed_incidents(db_session, count=1)
        resp = await api_client.get(f"/api/v1/incidents/{incidents[0].id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["root_cause"] is None
        assert data["recommendations"] == []


class TestMetricsEndpoint:
    @pytest.mark.asyncio
    async def test_metrics_returns_correct_totals(
        self, api_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        await _seed_incidents(db_session, count=3)

        resp = await api_client.get("/api/v1/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_incidents"] >= 3

    @pytest.mark.asyncio
    async def test_metrics_by_status_sums_to_total(
        self, api_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        await _seed_incidents(db_session, count=3)

        resp = await api_client.get("/api/v1/metrics")
        assert resp.status_code == 200
        data = resp.json()
        by_status_sum = sum(s["count"] for s in data["by_status"])
        assert by_status_sum == data["total_incidents"]

    @pytest.mark.asyncio
    async def test_metrics_empty_db_returns_zeros(self, api_client: AsyncClient) -> None:
        resp = await api_client.get("/api/v1/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_incidents"] == 0
        assert data["total_analyzed"] == 0
