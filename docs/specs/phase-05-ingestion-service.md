# Phase 5 — Ingestion Service

## Objective

Wire the Azure Monitor connector (Phase 4) into a production-ready ingestion loop: a
scheduled poller that fetches new exceptions and persists them as `Incident` records in
PostgreSQL. The Agent Worker polls PostgreSQL directly for new incidents; no message
broker is required.

> **Note (post-Phase 31):** The original design published `IncidentEvent` messages to
> Azure Service Bus after persistence. That dependency was removed to enable cloud-agnostic
> Helm chart distribution (Artifact Hub). PostgreSQL `status='new'` rows serve as the
> work queue; the Service Bus publisher and the `IncidentEvent` model are no longer part
> of this phase.

---

## Files to Create

| Path | Purpose |
|------|---------|
| `apps/worker/ingestion/scheduler.py` | `IngestionScheduler` — orchestrates poll → persist |
| `apps/worker/main.py` | Async worker entry-point; runs the scheduler or poller loop |
| `tests/integration/test_ingestion_scheduler.py` | Scheduler tests with mocked connector |

## Files to Modify

| Path | Change |
|------|--------|
| `apps/api/core/config.py` | Add `local_mode`, `ingestion_poll_interval_seconds`, `ingestion_lookback_minutes` settings |
| `ROADMAP.md` | Check off ingestion service milestone item |

---

## Dependencies

All already declared in `pyproject.toml`:
- `azure-identity = "^1.17"` — `DefaultAzureCredential`
- `pydantic = "^2.7"` — domain models + JSON serialisation
- `sqlalchemy = "^2.0"` — async ORM for PostgreSQL

---

## Implementation Notes

### IngestionScheduler

Single-run method + infinite poll loop:

```python
class IngestionScheduler:
    async def run_once(self) -> list[Incident]
    async def run_forever(self) -> None  # asyncio.sleep between runs
```

`run_once` flow:
1. Open an async DB session.
2. Create `AzureMonitorClient(workspace_id)`.
3. Create `IngestionConnector(session, monitor_client)`.
4. Call `connector.run(lookback_minutes)` → list of new `Incident` objects.
5. Commit the DB session.
6. Return the list of new incidents.

The Agent Worker (`LocalIncidentPoller`) polls PostgreSQL for rows where `status='new'`
and processes them through the LangGraph pipeline. No inter-service messaging is needed.

`run_forever` wraps `run_once` in a `try/except` so transient errors (network, Azure
API) do not crash the worker. Errors are logged; the loop sleeps
`ingestion_poll_interval_seconds` between runs regardless of success or failure.

### Worker Entry-point (`apps/worker/main.py`)

```python
async def main() -> None:
    configure_logging()
    scheduler = IngestionScheduler(settings=get_settings(), session_factory=...)
    await scheduler.run_forever()
```

Uses `asyncio.run(main())` so it can be launched as:
```
poetry run python -m apps.worker.main
```

### Error Handling

- Transient Azure errors (network, throttling): caught in `run_forever`, logged, loop continues.
- Fatal config errors (missing workspace ID): raise at startup before entering the loop.
- DB errors: session is rolled back; loop continues.

---

## Acceptance Criteria

- [ ] `pytest tests/integration/test_ingestion_scheduler.py -v` — all pass
- [ ] `ruff check apps/worker/` — no errors
- [ ] `mypy apps/worker/ --strict` — 0 errors
- [ ] Scheduler commits session only after connector succeeds
- [ ] Scheduler rolls back session on connector error
- [ ] No `azure-servicebus` import anywhere in `apps/` or `packages/`

---

## Commit Message

```
feat(worker): add IngestionScheduler and worker entry-point
```
