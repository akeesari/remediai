# Phase 23 — Structured Logging + OpenTelemetry Tracing

## Goal

Add distributed tracing across all three services (API, Agent Worker,
Ingestion Worker) using OpenTelemetry, and standardise structured JSON logging
with `correlation_id` and `incident_id` bound on every record.  Traces are
exported to Azure Monitor Application Insights.

---

## Background

`structlog` is already in use but logging is inconsistent across services.
No distributed trace propagation exists between the FastAPI API and the Agent
Worker.  This phase establishes a single observability standard.

---

## Deliverables

| Artifact | Description |
|---|---|
| `packages/observability/__init__.py` | Package init |
| `packages/observability/logging.py` | `configure_logging()` — structlog JSON renderer + OpenTelemetry log bridge |
| `packages/observability/tracing.py` | `configure_tracing(service_name)` — OTLP exporter to Azure Monitor |
| `packages/observability/middleware.py` | FastAPI middleware: extract trace context from headers, bind to structlog |
| Updated `apps/api/main.py` | Call `configure_logging()` and `configure_tracing("api")` at startup |
| Updated `apps/worker/ingestion/runner.py` | Call `configure_logging()` and `configure_tracing("ingestion-worker")` |
| Updated `apps/worker/agents/runner.py` | Call `configure_logging()` and `configure_tracing("agent-worker")` |
| Updated `packages/agent_runtime/` agents | Use `logger.bind(trace_id=..., span_id=...)` where relevant |
| `pyproject.toml` update | Add `opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-exporter-otlp`, `azure-monitor-opentelemetry-exporter` |
| `tests/unit/test_logging.py` | Unit tests: JSON output format, correlation_id binding |

---

## Logging Standard

### Output Format

All log records must be emitted as single-line JSON:

```json
{
  "timestamp": "2026-05-24T10:00:00.123Z",
  "level": "info",
  "event": "pipeline_started",
  "service": "agent-worker",
  "correlation_id": "corr-abc-123",
  "incident_id": "inci-xyz-789",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7"
}
```

### `configure_logging()` Responsibilities

1. Configure `structlog` with `JSONRenderer` (not `ConsoleRenderer`) in
   production; `ConsoleRenderer` with colours when `LOG_FORMAT=console`
   (local dev).
2. Set the standard log level from `settings.log_level` (default `"INFO"`).
3. Bridge OpenTelemetry log records into structlog so trace context is
   automatically injected.
4. Replace the root Python `logging` handler so third-party library logs
   (SQLAlchemy, httpx) also emit JSON.

### Mandatory Context Fields

Every log record must include:

| Field | Source |
|---|---|
| `service` | Set once at startup via `configure_logging(service_name=...)` |
| `correlation_id` | Bound per-request (FastAPI middleware) or per-message (Service Bus handler) |
| `incident_id` | Bound per-incident inside each agent node |
| `trace_id` | Injected from active OpenTelemetry span |
| `span_id` | Injected from active OpenTelemetry span |

---

## Tracing Standard

### Spans to Create

| Service | Span | Attributes |
|---|---|---|
| API | Per HTTP request | `http.method`, `http.route`, `http.status_code` |
| Agent Worker | Per pipeline run | `incident_id`, `correlation_id` |
| Agent Worker | Per agent node | `agent.name`, `agent.prompt_version`, `agent.latency_ms` |
| Ingestion Worker | Per KQL poll cycle | `incidents.found`, `incidents.new` |
| Ingestion Worker | Per Service Bus publish | `message.id`, `topic.name` |

### `configure_tracing(service_name)` Responsibilities

1. Initialise `TracerProvider` with `BatchSpanProcessor`.
2. Export spans to Azure Monitor via `AzureMonitorTraceExporter`
   (connection string from `settings.applicationinsights_connection_string`).
3. Also export to `OTLPSpanExporter` if `OTLP_ENDPOINT` is set (for local
   Jaeger / Tempo debugging).
4. Auto-instrument FastAPI (`FastAPIInstrumentor`) and SQLAlchemy
   (`SQLAlchemyInstrumentor`) when present.
5. Propagate W3C TraceContext headers (`traceparent`, `tracestate`) on all
   outbound HTTP calls (httpx instrumentation).

---

## FastAPI Middleware (`middleware.py`)

```python
class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-Id", str(uuid4()))
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        response = await call_next(request)
        response.headers["X-Correlation-Id"] = correlation_id
        structlog.contextvars.clear_contextvars()
        return response
```

---

## Configuration Additions

New settings in `packages/config/settings.py`:

```python
log_level: str = "INFO"
log_format: str = "json"               # "json" | "console"
applicationinsights_connection_string: str = ""
otlp_endpoint: str = ""               # Optional; for local dev tracing
```

---

## Unit Tests (`test_logging.py`)

| Test | Asserts |
|---|---|
| `test_json_output_contains_required_fields` | Captured log output includes `timestamp`, `level`, `event`, `service` |
| `test_correlation_id_bound_per_request` | Two concurrent requests have different `correlation_id` values |
| `test_incident_id_bound_in_agent_context` | Log emitted inside agent node contains `incident_id` |
| `test_console_format_when_env_set` | `LOG_FORMAT=console` produces non-JSON output |

---

## Acceptance Criteria

- `ruff check .` and `mypy apps/ packages/ --strict` pass.
- All existing tests continue to pass.
- Running the API locally: every HTTP log line is valid JSON with all required fields.
- `correlation_id` is consistent across all log lines for a single request.
- OpenTelemetry spans appear in Azure Monitor Application Insights (verified
  with a manual test against a real Application Insights instance).

---

## Out of Scope

- Custom Prometheus metrics endpoint (Milestone 8 stretch goal).
- Grafana dashboard provisioning.
- Log aggregation pipeline configuration (Azure Log Analytics workspace setup).
