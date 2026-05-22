# Phase 3 — PostgreSQL Schema & Alembic Migrations

## Objective

Create the persistence layer: SQLAlchemy 2.0 async ORM models mapping to the four PostgreSQL
tables defined in ARCHITECTURE.md, an async session factory, and an Alembic migration that creates
the schema from scratch. This unblocks every service that reads or writes incident data.

---

## Files to Create

| Path | Purpose |
|------|---------|
| `packages/data_access/base.py` | `DeclarativeBase` shared by all ORM models |
| `packages/data_access/models/incident_orm.py` | `IncidentOrm` — maps to `incidents` table |
| `packages/data_access/models/analysis_orm.py` | `AnalysisOrm` — maps to `incident_analyses` table |
| `packages/data_access/models/work_item_orm.py` | `WorkItemOrm` — maps to `work_items` table |
| `packages/data_access/models/audit_log_orm.py` | `AuditLogOrm` — maps to `audit_log` table |
| `packages/data_access/models/__init__.py` | Re-exports all four ORM models |
| `packages/data_access/session.py` | Async engine + session factory + `get_db_session` |
| `alembic.ini` | Alembic configuration |
| `alembic/env.py` | Async-compatible migration environment |
| `alembic/script.py.mako` | Revision file template |
| `alembic/versions/0001_initial_schema.py` | Migration creating all four tables |
| `tests/unit/test_data_access_models.py` | Unit tests for ORM models (no DB required) |

## Files to Modify

| Path | Change |
|------|--------|
| `packages/data_access/__init__.py` | Re-export ORM models + session utilities |
| `pyproject.toml` | Add SQLAlchemy mypy plugin |
| `Makefile` | Add `migrate` and `migrate-down` targets |
| `ROADMAP.md` | Check off PostgreSQL schema milestone item |

---

## Dependencies

All already declared in `pyproject.toml`:
- `sqlalchemy = "^2.0"` (includes async support + mypy stubs)
- `alembic = "^1.13"`
- `asyncpg = "^0.29"`

---

## Implementation Notes

### ORM model conventions

- Class suffix `Orm` to distinguish from Pydantic domain models (`IncidentOrm` vs `Incident`)
- All inherit from `packages.data_access.base.Base` (shared `DeclarativeBase`)
- Use `Mapped[X]` + `mapped_column(...)` (SQLAlchemy 2.0 typed API)
- `Mapped[str | None]` implies `nullable=True`; `Mapped[str]` implies `nullable=False`
- UUID primary keys: `mapped_column(PG_UUID(as_uuid=True), primary_key=True)`
- JSON/array columns: `JSONB` from `sqlalchemy.dialects.postgresql`
- Timestamps: `DateTime(timezone=True)` — always timezone-aware
- Relationships use string forward references to avoid circular imports

### Table → domain model field mapping

**incidents**

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| correlation_id | UUID | |
| source | VARCHAR(255) | |
| exception_type | VARCHAR(500) | |
| exception_message | TEXT | |
| stack_trace | TEXT NULL | |
| fingerprint | VARCHAR(64) | UNIQUE index |
| priority | VARCHAR(20) | default "medium" |
| status | VARCHAR(30) | default "new" |
| raw_payload | JSONB | default {} |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

**incident_analyses**

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| incident_id | UUID FK | → incidents.id ON DELETE CASCADE |
| root_cause | TEXT NULL | |
| root_cause_json | JSONB NULL | serialised RootCauseJson |
| recommendations | JSONB | list of Recommendation dicts |
| code_snippets | JSONB | list of CodeSnippet dicts |
| rag_results | JSONB | list of RAGResult dicts |
| agent_trace | JSONB | list of AgentTraceEntry dicts |
| created_at | TIMESTAMPTZ | |

**work_items**

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| incident_id | UUID FK | → incidents.id ON DELETE CASCADE |
| item_type | VARCHAR(20) | default "bug" |
| ado_item_id | INTEGER | |
| ado_item_url | VARCHAR(1000) | |
| pr_url | VARCHAR(1000) NULL | |
| pr_branch | VARCHAR(255) NULL | |
| created_at | TIMESTAMPTZ | |

**audit_log**

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| incident_id | UUID FK NULL | → incidents.id ON DELETE SET NULL |
| agent_name | VARCHAR(100) | |
| action | VARCHAR(255) | |
| actor_identity | VARCHAR(255) NULL | |
| metadata | JSONB | default {} |
| timestamp | TIMESTAMPTZ | |

### Indexes

```sql
CREATE UNIQUE INDEX ix_incidents_fingerprint ON incidents (fingerprint);
CREATE INDEX ix_incident_analyses_incident_id ON incident_analyses (incident_id);
CREATE INDEX ix_work_items_incident_id ON work_items (incident_id);
CREATE INDEX ix_audit_log_incident_id ON audit_log (incident_id);
CREATE INDEX ix_audit_log_timestamp ON audit_log (timestamp);
```

### Session factory

`session.py` exposes:
- `async_session_factory: async_sessionmaker[AsyncSession]` — module-level singleton
- `get_db_session() -> AsyncGenerator[AsyncSession, None]` — FastAPI dependency that
  auto-commits on success, rolls back on exception

### Alembic async setup

`env.py` reads the database URL from `DATABASE_URL` env var (falls back to
`alembic.ini` `sqlalchemy.url`). Uses `AsyncConnection.run_sync()` for the online
migration path.

---

## Acceptance Criteria

- [ ] `pytest tests/unit/test_data_access_models.py -v` — all tests pass
- [ ] `ruff check packages/data_access/ alembic/` — no lint errors
- [ ] `mypy packages/data_access/ --strict` — 0 errors
- [ ] All four ORM models have the correct `__tablename__`
- [ ] `IncidentOrm.fingerprint` has a unique index
- [ ] `AnalysisOrm`, `WorkItemOrm`, `AuditLogOrm` each have a FK index to `incidents`
- [ ] `alembic check` or manual review confirms migration covers all columns

---

## Commit Message

```
feat(data-access): add SQLAlchemy ORM models, session factory, and Alembic migration
```
