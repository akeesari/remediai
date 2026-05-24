"""E2E test fixtures.

Requires a running PostgreSQL instance.  Set TEST_DATABASE_URL to point at a
dedicated test database (separate from the dev database).  Alembic migrations
run once per session; each test is wrapped in a savepoint that is rolled back
on teardown so no data persists between tests.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import AIMessage
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from apps.api.main import app
from packages.agent_runtime.pipeline import build_pipeline
from packages.data_access.models.analysis_orm import AnalysisOrm
from packages.data_access.models.incident_orm import IncidentOrm
from packages.data_access.models.work_item_orm import WorkItemOrm
from packages.data_access.session import get_db_session
from packages.domain.models.agent_state import IncidentState

_DEFAULT_TEST_DB_URL = (
    "postgresql+asyncpg://remediai:change_me_locally@localhost:5432/remediai_test"
)

_RC_JSON = json.dumps(
    {
        "root_cause_summary": "Unguarded null reference in the service layer.",
        "root_cause_json": {
            "component": "UserService.GetById",
            "likely_cause": "Missing null check before dereferencing.",
            "contributing_factors": ["No null guard"],
            "confidence": 0.82,
        },
        "evidence": ["Top frame points to UserService"],
    }
)

_FP_JSON = json.dumps(
    {
        "recommendations": [
            {
                "rank": 1,
                "title": "Add null guard in UserService.GetById",
                "description": "Check for null before accessing the return value.",
                "affected_files": ["src/services/UserService.cs"],
                "suggested_change": "if (user == null) throw new NotFoundException(id);",
                "confidence": 0.85,
                "source_refs": [],
            }
        ]
    }
)


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def run_migrations() -> None:
    """Run Alembic migrations against the test database (sync, session-scoped)."""
    test_db_url = os.environ.get("TEST_DATABASE_URL", _DEFAULT_TEST_DB_URL)
    os.environ["DATABASE_URL"] = test_db_url
    cfg = AlembicConfig("alembic.ini")
    alembic_command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
async def db_engine(run_migrations: None) -> AsyncGenerator[AsyncEngine, None]:
    test_db_url = os.environ.get("TEST_DATABASE_URL", _DEFAULT_TEST_DB_URL)
    engine = create_async_engine(test_db_url, echo=False, pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest.fixture()
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Each test runs inside a transaction that is rolled back on teardown."""
    async with db_engine.connect() as conn:
        await conn.begin()
        factory = async_sessionmaker(
            conn,
            join_transaction_mode="create_savepoint",
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with factory() as session:
            yield session
        await conn.rollback()


@pytest.fixture()
async def api_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """FastAPI test client wired to the rollback-wrapped DB session."""

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = _override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Pipeline fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_pipeline() -> object:
    """Full pipeline with mocked LLM (rule path: 2 calls), ADO, Search, Boards."""
    llm = MagicMock()
    llm.ainvoke = AsyncMock(side_effect=[AIMessage(content=_RC_JSON), AIMessage(content=_FP_JSON)])
    ado = MagicMock()
    ado.repository = "test-repo"
    ado.get_file_content = AsyncMock(return_value=None)
    ado.get_latest_commit_sha = AsyncMock(return_value="abc123")
    search = MagicMock()
    search.search = AsyncMock(return_value=[])
    boards = MagicMock()
    boards.create_bug = AsyncMock(
        return_value={
            "id": 9001,
            "_links": {"html": {"href": "https://dev.azure.com/test/9001"}},
        }
    )
    return build_pipeline(llm=llm, ado_client=ado, search_client=search, boards_client=boards)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_incident_orm(
    exception_type: str = "System.NullReferenceException",
    priority: str = "high",
    status: str = "new",
) -> IncidentOrm:
    now = datetime.now(UTC)
    return IncidentOrm(
        id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        source="test-app",
        exception_type=exception_type,
        exception_message="Object reference not set to an instance of an object.",
        stack_trace=(
            "   at UserService.GetById(Int32 id) in /src/services/UserService.cs:line 42\n"
            "   at OrderService.Process(Order o) in /src/services/OrderService.cs:line 100"
        ),
        fingerprint=str(uuid.uuid4()),
        priority=priority,
        status=status,
        raw_payload={},
        created_at=now,
        updated_at=now,
    )


async def run_and_persist(
    pipeline: object,
    session: AsyncSession,
    incident: IncidentOrm,
) -> IncidentState:
    """Run the pipeline and persist results — mirrors what the agent worker does."""
    state: IncidentState = {
        "incident_id": str(incident.id),
        "correlation_id": str(incident.correlation_id),
        "exception_type": incident.exception_type,
        "exception_message": incident.exception_message,
        "stack_trace": incident.stack_trace or "",
        "raw_payload": dict(incident.raw_payload),
        "agent_trace": [],
        "errors": [],
        "triage_labels": [],
    }
    result: IncidentState = await pipeline.ainvoke(state)  # type: ignore[attr-defined]

    incident.status = "analyzed"
    if result.get("priority"):
        incident.priority = result["priority"]

    analysis = AnalysisOrm(
        id=uuid.uuid4(),
        incident_id=incident.id,
        root_cause=result.get("root_cause_summary"),
        root_cause_json=result.get("root_cause_json"),
        recommendations=list(result.get("recommendations") or []),
        code_snippets=list(result.get("code_snippets") or []),
        rag_results=list(result.get("rag_results") or []),
        agent_trace=list(result.get("agent_trace") or []),
        created_at=datetime.now(UTC),
    )
    session.add(analysis)

    ado_bug_id = result.get("ado_bug_id")
    ado_bug_url = result.get("ado_bug_url")
    if ado_bug_id:
        work_item = WorkItemOrm(
            id=uuid.uuid4(),
            incident_id=incident.id,
            item_type="bug",
            ado_item_id=int(ado_bug_id),
            ado_item_url=str(ado_bug_url or ""),
            created_at=datetime.now(UTC),
        )
        session.add(work_item)

    await session.flush()
    return result
