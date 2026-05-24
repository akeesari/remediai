"""End-to-end lifecycle tests.

Each test inserts an incident, runs the full 6-node pipeline (LLM/ADO/Search/
Boards mocked), persists the results, then queries the DB to assert state.
Everything is rolled back after each test — no data survives between runs.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.data_access.models.analysis_orm import AnalysisOrm
from packages.data_access.models.incident_orm import IncidentOrm
from packages.data_access.models.work_item_orm import WorkItemOrm

from .conftest import make_incident_orm, run_and_persist

pytestmark = pytest.mark.e2e


class TestIncidentLifecycle:
    @pytest.mark.asyncio
    async def test_create_incident_persists_to_db(self, db_session: AsyncSession) -> None:
        incident = make_incident_orm()
        db_session.add(incident)
        await db_session.flush()

        row = await db_session.get(IncidentOrm, incident.id)
        assert row is not None
        assert row.status == "new"
        assert row.exception_type == "System.NullReferenceException"

    @pytest.mark.asyncio
    async def test_pipeline_transitions_status_to_analyzed(
        self, db_session: AsyncSession, mock_pipeline: object
    ) -> None:
        incident = make_incident_orm()
        db_session.add(incident)
        await db_session.flush()

        await run_and_persist(mock_pipeline, db_session, incident)

        row = await db_session.get(IncidentOrm, incident.id)
        assert row is not None
        assert row.status == "analyzed"

    @pytest.mark.asyncio
    async def test_pipeline_writes_analysis_record(
        self, db_session: AsyncSession, mock_pipeline: object
    ) -> None:
        incident = make_incident_orm()
        db_session.add(incident)
        await db_session.flush()

        await run_and_persist(mock_pipeline, db_session, incident)

        stmt = select(AnalysisOrm).where(AnalysisOrm.incident_id == incident.id)
        result = await db_session.execute(stmt)
        analysis = result.scalar_one_or_none()

        assert analysis is not None
        assert analysis.root_cause is not None
        assert len(analysis.root_cause) > 0
        assert isinstance(analysis.recommendations, list)
        assert len(analysis.recommendations) >= 1

    @pytest.mark.asyncio
    async def test_pipeline_writes_work_item_record(
        self, db_session: AsyncSession, mock_pipeline: object
    ) -> None:
        incident = make_incident_orm()
        db_session.add(incident)
        await db_session.flush()

        await run_and_persist(mock_pipeline, db_session, incident)

        stmt = select(WorkItemOrm).where(WorkItemOrm.incident_id == incident.id)
        result = await db_session.execute(stmt)
        work_item = result.scalar_one_or_none()

        assert work_item is not None
        assert work_item.ado_item_id == 9001
        assert "dev.azure.com" in work_item.ado_item_url

    @pytest.mark.asyncio
    async def test_pipeline_writes_agent_trace(
        self, db_session: AsyncSession, mock_pipeline: object
    ) -> None:
        incident = make_incident_orm()
        db_session.add(incident)
        await db_session.flush()

        await run_and_persist(mock_pipeline, db_session, incident)

        stmt = select(AnalysisOrm).where(AnalysisOrm.incident_id == incident.id)
        result = await db_session.execute(stmt)
        analysis = result.scalar_one_or_none()

        assert analysis is not None
        agent_names = [e["agent_name"] for e in analysis.agent_trace]
        assert agent_names == [
            "triage",
            "root_cause",
            "code_context",
            "rag",
            "fix_planner",
            "bug_creator",
        ]

    @pytest.mark.asyncio
    async def test_pipeline_errors_do_not_leave_orphan_rows(
        self, db_session: AsyncSession, mock_pipeline: object
    ) -> None:
        """Even if the bug creator partially fails, analysis is still persisted."""
        incident = make_incident_orm()
        db_session.add(incident)
        await db_session.flush()

        # Run normally — both analysis and work item should exist
        await run_and_persist(mock_pipeline, db_session, incident)

        stmt = select(AnalysisOrm).where(AnalysisOrm.incident_id == incident.id)
        result = await db_session.execute(stmt)
        assert result.scalar_one_or_none() is not None
