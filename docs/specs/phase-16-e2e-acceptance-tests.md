# Phase 16 — End-to-End Acceptance Tests

## Goal

Validate the complete incident lifecycle — from creation through pipeline
analysis to ADO bug creation — against a real PostgreSQL instance running in
Docker Compose.  This closes the only remaining Milestone 5 item and gives
a regression harness that covers all six pipeline nodes together.

---

## Background

Existing tests mock the database entirely.  This phase adds a dedicated test
suite that spins up a real Postgres container, runs Alembic migrations, and
exercises the full stack:

```
HTTP POST /api/v1/incidents (test endpoint)
  → IncidentOrm row created in Postgres
  → AgentPipelineRunner invoked in-process
  → IncidentAnalysisOrm + WorkItemOrm rows created
  → GET /api/v1/incidents/{id} returns root_cause, recommendations, ado_bug_url
```

The LLM, ADO Repos, AI Search, and ADO Boards clients remain mocked —
only the database layer is real.

---

## Deliverables

| Artifact | Description |
|---|---|
| `tests/e2e/conftest.py` | pytest fixtures: real async DB session, seeded test data, FastAPI test client |
| `tests/e2e/test_incident_lifecycle.py` | Full lifecycle test — create, analyze, assert state transitions |
| `tests/e2e/test_api_contract.py` | HTTP-level contract tests against the real FastAPI app + real DB |
| `pyproject.toml` update | Add `test-e2e` pytest marker; add `asyncpg` test dependency |
| `Makefile` update | Add `test-e2e` target: `$(PYTHON) -m pytest tests/e2e/ -v` |

---

## Test Environment

- PostgreSQL started by Docker Compose (`docker-compose.dev.yml`).
- `TEST_DATABASE_URL` environment variable points to the test database
  (separate from the dev database to avoid data pollution).
- If the configured test database does not yet exist, the session fixture
  creates it before running Alembic migrations.
- Alembic migrations run once per test session via a session-scoped fixture.
- Each test function runs inside a transaction that is rolled back on teardown
  (no persistent state between tests).

---

## Fixtures (`tests/e2e/conftest.py`)

```python
@pytest.fixture()
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create engine, run migrations, yield, drop all."""

@pytest.fixture()
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Wrap each test in a savepoint; roll back after."""

@pytest.fixture()
def api_client(db_session) -> AsyncGenerator[AsyncClient, None]:
    """httpx.AsyncClient with ASGITransport; overrides get_db_session dep."""

@pytest.fixture()
def mock_pipeline() -> MagicMock:
    """Pipeline with mocked LLM + ADO + Search + Boards clients."""
```

---

## Test Cases

### `test_incident_lifecycle.py`

| Test | Asserts |
|---|---|
| `test_create_incident_persists_to_db` | POST creates `IncidentOrm` row; `status == "new"` |
| `test_pipeline_transitions_status_to_analyzed` | After pipeline run, `status == "analyzed"` |
| `test_pipeline_writes_analysis_record` | `IncidentAnalysisOrm` row exists with non-null `root_cause` |
| `test_pipeline_writes_work_item_record` | `WorkItemOrm` row exists with `ado_item_id == 9001` |
| `test_pipeline_writes_agent_trace` | `agent_trace` JSON contains all 6 agent names in order |
| `test_pipeline_errors_do_not_leave_orphan_rows` | Error during bug creation still persists analysis row |

### `test_api_contract.py`

| Test | Asserts |
|---|---|
| `test_list_incidents_returns_paginated_shape` | Response matches `PaginatedResponse` schema |
| `test_list_incidents_filter_by_priority` | Only incidents with matching priority returned |
| `test_list_incidents_filter_by_status` | Only incidents with matching status returned |
| `test_get_incident_detail_returns_full_shape` | All `IncidentDetail` fields present |
| `test_get_incident_404_on_missing` | Returns 404 for unknown UUID |
| `test_metrics_returns_correct_totals` | `total_incidents` matches seeded count |
| `test_metrics_by_status_correct` | `by_status` breakdown sums to `total_incidents` |

---

## Acceptance Criteria

- `make test-e2e` passes against a running Docker Compose Postgres.
- All existing `make test` (unit + agent-evals) tests continue to pass unaffected.
- No test writes permanent state — every test is isolated via savepoint rollback.
- `ruff check .` and `mypy apps/ packages/ --strict` pass with new files included.

---

## Out of Scope

- Testing against Azure services (Service Bus, AI Search, ADO) — those remain mocked.
- Performance / load testing — covered in Phase 28.
- UI-level end-to-end tests (browser automation) — not required for MVP.
