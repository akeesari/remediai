# Phase 22b — Local Log Bridge

## Goal

Add a `LOCAL_MODE=true` development mode so engineers can test the full
RemediAI pipeline locally — without any Azure Monitor / Application Insights
dependency — by monitoring exceptions emitted to Docker container stdout and
routing them through the same Service Bus → Agent Worker → dashboard flow
that production uses.

When `LOCAL_MODE=true`:
- A new `log-bridge` container tails stdout from the `api`, `worker`, and
  `dashboard` containers via the Docker socket.
- Python tracebacks and HTTP 5xx lines are parsed and POSTed to the API as
  raw exception payloads.
- The API creates `incidents` rows (with fingerprint deduplication) and stores
  raw log lines in Redis for the dashboard.
- The worker polls Postgres for `status=new` incidents (instead of Azure
  Monitor) and runs the existing LangGraph agent pipeline.
- A new **Logs** tab in the React dashboard shows live container logs with
  exception lines highlighted and a link to the created incident.

---

## Deliverables

| Artifact | Description |
|---|---|
| `docs/specs/phase-22b-local-log-bridge.md` | This spec |
| `apps/log_bridge/Dockerfile` | Standalone image — `docker`, `redis`, `httpx`, `structlog` |
| `apps/log_bridge/requirements.txt` | Bridge-only pip deps |
| `apps/log_bridge/main.py` | Entry point — starts one tailer thread per watched container |
| `apps/log_bridge/exception_parser.py` | Stateful Python-traceback parser |
| `apps/log_bridge/log_tailer.py` | Docker SDK log-stream reader (per container) |
| `apps/api/routers/local_logs.py` | `POST /api/v1/local/ingest`, `GET /api/v1/local/logs` |
| `apps/api/core/config.py` | Add `local_mode: bool` setting |
| `apps/api/main.py` | Register `local_logs` router when `LOCAL_MODE=true` |
| `apps/worker/agents/local_poller.py` | Polls Postgres for new incidents; runs agent pipeline |
| `apps/worker/main.py` | Branch on `local_mode` — use poller instead of scheduler |
| `docker-compose.local.yml` | Add `log-bridge` service with docker-socket mount |
| `.env` | Document `LOCAL_MODE=true` |
| `Makefile` | Add `local-bridge-restart` target |
| `apps/dashboard/src/pages/LocalLogsPage.tsx` | Live log viewer with exception highlights |
| `apps/dashboard/src/api/localLogs.ts` | API client for log lines |
| `apps/dashboard/src/types/localLogs.ts` | TypeScript types |
| `apps/dashboard/src/App.tsx` | Add `/logs` route |
| `apps/dashboard/src/components/Layout.tsx` | Add **Logs** nav link |

---

## Security Touchpoints

- Does this phase make an LLM call? **No** (the bridge does not; the existing
  pipeline does, and `scrub()` is already applied there).
- Does this phase write agent decisions? **No** new agents — existing pipeline
  is reused unchanged.
- Does this phase introduce a new credential? **No** — only `LOCAL_MODE` env
  var (boolean, not a secret).
- Does this phase expose a new HTTP endpoint? **Yes** — `POST /local/ingest`
  and `GET /local/logs`. Both are only registered when `LOCAL_MODE=true`.
  Authentication is deferred (same as all other local-only endpoints); they
  must never be deployed to production.

---

## Data Flow (Local Mode)

```
Docker containers (api / worker / dashboard)
    │ stdout via /var/run/docker.sock
    ▼
log-bridge container
    │ stores all log lines → Redis LPUSH local:logs (ring buffer, 1 000 lines)
    │ on exception detected →
    ▼
POST /api/v1/local/ingest
    │ deduplicates by fingerprint → inserts into incidents table
    ▼
Worker LocalIncidentPoller (polls Postgres every 10 s for status=new)
    │ runs existing LangGraph pipeline (Triage → Root Cause → ... → Bug Creation)
    ▼
Postgres → FastAPI → React dashboard (Incidents tab, existing flow)

GET /api/v1/local/logs
    │ reads Redis LRANGE local:logs 0 199
    ▼
React dashboard → new Logs tab
```

---

## Exception Detection Rules

The parser handles three patterns in priority order:

1. **Python traceback** — multi-line state machine:
   - Trigger: line contains `Traceback (most recent call last):`
   - Accumulate lines until one matches `^ExceptionType: message$`
   - Extract `exception_type` and `exception_message` from the final line
   - `stack_trace` = all accumulated lines joined

2. **Single-line exception** — matches `^SomethingError: message` without a
   preceding traceback (e.g. `RuntimeError: cannot connect to database`).

3. **HTTP 5xx in uvicorn access log** — matches
   `"METHOD /path HTTP/1.1" 5XX` pattern. Emits `HTTPException` with the
   status code in the message.

---

## Redis Schema

| Key | Type | TTL | Contents |
|---|---|---|---|
| `local:logs` | List | none (LTRIM 0–999) | JSON `LogLine` objects, newest first |

```json
{
  "ts": "2026-05-24T12:00:00Z",
  "container": "api",
  "line": "Traceback (most recent call last):",
  "level": "ERROR",
  "is_exception": true,
  "incident_id": "uuid-or-null"
}
```

---

## API Contract

### `POST /api/v1/local/ingest`

Request:
```json
{
  "container": "api",
  "exception_type": "ValueError",
  "exception_message": "invalid literal for int() with base 10: 'abc'",
  "stack_trace": "Traceback (most recent call last):\n  ...\nValueError: invalid literal",
  "source": "local-docker"
}
```

Response (new):
```json
{ "status": "created", "incident_id": "<uuid>" }
```

Response (duplicate):
```json
{ "status": "duplicate", "incident_id": null }
```

### `GET /api/v1/local/logs?container=api&limit=200`

Response:
```json
[
  {
    "ts": "2026-05-24T12:00:00Z",
    "container": "api",
    "line": "ValueError: invalid literal",
    "level": "ERROR",
    "is_exception": true,
    "incident_id": "abc-123"
  }
]
```

---

## Acceptance Criteria

- `docker compose -f docker-compose.local.yml up` starts the `log-bridge`
  container alongside all other services.
- Introducing a Python `raise ValueError("test-local-exception")` in the API
  causes an incident to appear in the Incidents tab within 30 s.
- The Logs tab at `http://localhost:3000/logs` shows live container log lines,
  with exception rows highlighted in red.
- Exception rows link to the created incident detail page.
- Setting `LOCAL_MODE=false` (or omitting it) does NOT register the
  `/local/*` endpoints and does NOT start the local poller in the worker.
- The log-bridge container does not start in production (`docker-compose.local.yml`
  is never used outside local dev).
- `make local-bridge-e2e` passes all tests without manual intervention.

---

## End-to-End Testing

### Why pytest, not a custom AI agent

The e2e tests are **automated pytest tests** that run against the live local
stack — not a Claude Code agent. This is the right choice because:

- Pytest is deterministic, version-controlled, and CI-compatible
- Agent-based testing is non-deterministic and requires human oversight
- `make local-bridge-e2e` gives a binary pass/fail with zero involvement

Use the Claude Code `/verify` skill only for **visual browser verification**
after the automated tests pass.

---

### Test files

| File | Type | Needs Docker? |
|---|---|---|
| `tests/unit/test_exception_parser.py` | Unit | No — pure regex logic |
| `tests/e2e/test_local_log_bridge.py` | Live stack | Yes — `make local-up` |

---

### Unit tests (`make test-unit`)

`tests/unit/test_exception_parser.py` covers 16 cases across three test classes:

| Class | What it tests |
|---|---|
| `TestTraceback` | Multi-line Python traceback detection, timestamp stripping, level-prefix stripping, reset after completion, runaway cap |
| `TestSingleLine` | Single-line `ExcType: message` detection, false-positive guards |
| `TestHttp5xx` | Uvicorn access-log 5xx detection, 200/404 ignored |

Run independently (no Docker, no network):
```bash
pytest tests/unit/test_exception_parser.py -v
```

---

### Live stack e2e tests (`make local-bridge-e2e`)

**Prerequisites:**
```bash
make local-up          # start all 6 containers (api, worker, dashboard, postgres, redis, log-bridge)
make local-migrate     # apply Alembic migrations
# Wait ~30s for log-bridge to connect to docker socket
```

**Run:**
```bash
make local-bridge-e2e
# or with custom timeouts:
BRIDGE_POLL_TIMEOUT=60 PIPELINE_TIMEOUT=180 make local-bridge-e2e
```

**Test classes and what each verifies:**

#### `TestLogBridgeDetection` — infrastructure up checks
| Test | What it proves |
|---|---|
| `test_logs_endpoint_is_reachable` | `GET /api/v1/local/logs` returns 200 → `LOCAL_MODE=true` confirmed |
| `test_dev_throw_returns_500` | `GET /api/v1/local/dev/throw` returns 500 → exception endpoint is live |

#### `TestFullBridgePipeline` — core bridge flow (no Azure credentials needed)
| Test | What it proves |
|---|---|
| `test_exception_creates_incident` | Exception in API container → incident row in Postgres within `BRIDGE_POLL_TIMEOUT` (45s default) |
| `test_exception_line_appears_in_logs_endpoint` | Log line with `is_exception=true` and correct container/level appears in `/api/v1/local/logs` |
| `test_exception_log_line_links_to_incident` | `incident_id` on the log line resolves to a real incident in `/api/v1/incidents/{id}` |
| `test_deduplication_prevents_duplicate_incidents` | Two identical exceptions within 1s produce exactly 1 incident |

#### `TestAgentPipeline` — pipeline completion (requires `AZURE_OPENAI_ENDPOINT`)
| Test | What it proves |
|---|---|
| `test_incident_transitions_to_analyzed` | Incident status moves from `new`→`analyzed` within `PIPELINE_TIMEOUT` (120s default); `root_cause` and `recommendations` are non-empty |

Tests in `TestAgentPipeline` auto-skip if `AZURE_OPENAI_ENDPOINT` is not set —
the bridge and incident creation tests always run.

**Environment overrides:**

| Variable | Default | Purpose |
|---|---|---|
| `LOCAL_API_URL` | `http://localhost:8000` | Override if API port differs |
| `BRIDGE_POLL_TIMEOUT` | `45` | Max seconds to wait for bridge detection |
| `PIPELINE_TIMEOUT` | `120` | Max seconds to wait for agent pipeline |

---

### How each test triggers the full flow

```
pytest calls GET /api/v1/local/dev/throw?marker=<uuid>
    ↓
FastAPI raises ValueError("local-bridge-test: <uuid>")
    ↓
uvicorn logs full Python traceback to stderr
    ↓
Docker captures stderr as container stdout
    ↓
log-bridge ContainerLogTailer reads the line (~1–2 s lag)
    ↓
ExceptionParser detects the traceback pattern
    ↓
bridge.py POSTs to POST /api/v1/local/ingest
    ↓
API creates incident row in Postgres (fingerprinted, deduplicated)
API stores log line in Redis with is_exception=True and incident_id
    ↓
pytest polls GET /api/v1/incidents until marker appears (≤45 s)
pytest polls GET /api/v1/local/logs until log line appears (≤45 s)
    ↓  [if AZURE_OPENAI_ENDPOINT set]
LocalIncidentPoller picks up incident (polls every 10 s)
Runs LangGraph pipeline → writes analysis to Postgres
    ↓
pytest polls GET /api/v1/incidents/{id} until status != new/triaging (≤120 s)
```

---

### Makefile targets

| Target | What it does |
|---|---|
| `make local-bridge-e2e` | Runs all `local_bridge`-marked tests against `localhost:8000` |
| `make local-bridge-logs` | Tails the log-bridge container output for debugging |
| `make local-bridge-restart` | Restarts just the log-bridge container (useful after code changes) |

---

## Out of Scope

- Alerting / paging (Phase 25).
- TLS or authentication for local endpoints.
- Windows / non-Linux Docker socket path (assumes `/var/run/docker.sock`).
- Log aggregation for CI (the bridge is local-only).
