# Phase 31 — Grafana / Loki Log Source Connector

## Goal

Add a second log ingestion path that polls Grafana Loki for application
exceptions, enabling teams who use the Grafana / Loki stack (instead of
Azure Monitor) to use RemediAI without migrating their observability
infrastructure.

---

## Background

SPEC.md Non-Goals list Grafana / Loki as out of MVP scope.  Milestone 9
extends the ingestion layer.  The agent pipeline, database, and dashboard
are unchanged.  Only the ingestion service gains a new connector.

---

## Deliverables

| Artifact | Description |
|---|---|
| `packages/connectors/loki/client.py` | `LokiClient` — async HTTP client wrapping the Loki HTTP API |
| `packages/connectors/loki/query_builder.py` | `build_exception_query(config)` — generates LogQL exception filter queries |
| `packages/connectors/loki/exception_extractor.py` | `extract_exceptions(loki_response)` — parses Loki stream values into `IncidentEvent` objects |
| `apps/worker/ingestion/loki_runner.py` | `LokiIngestionRunner` — polls Loki, deduplicates, publishes to Service Bus |
| Updated `apps/worker/ingestion/runner_factory.py` | Selects Azure Monitor or Loki runner based on `log_source` setting |
| Updated `packages/config/settings.py` | New `loki_*` settings |
| `tests/unit/test_loki_client.py` | Unit tests for Loki client with mock HTTP |
| `tests/unit/test_loki_exception_extractor.py` | Unit tests for LogQL response parsing |
| `docs/runbooks/loki-connector.md` | Operator guide for configuring the Loki connector |

---

## Loki HTTP API

RemediAI uses the Loki HTTP API (not the Grafana API):

- **Base URL**: configurable via `loki_base_url` setting.
- **Query endpoint**: `GET /loki/api/v1/query_range`
- **Auth**: Basic auth (username + API key from Key Vault) or bearer token.
- **Pagination**: `limit` + `start`/`end` timestamps.

---

## LogQL Query Strategy

### Exception Detection Query

```logql
{app=~"{{ app_name_pattern }}"} |= "Exception" | json | level = "error"
```

For structured JSON logs:
```logql
{app=~"{{ app_name_pattern }}"} | json | exception_type != ""
```

The query builder generates the correct form based on `loki_log_format`
setting (`"text"` or `"json"`).

---

## `LokiClient`

```python
class LokiClient:
    async def query_range(
        self,
        query: str,
        start: datetime,
        end: datetime,
        limit: int = 100,
    ) -> list[LokiStream]: ...
```

`LokiStream`:
```python
class LokiStream(BaseModel):
    labels: dict[str, str]
    values: list[tuple[str, str]]  # (nanosecond timestamp, log line)
```

---

## Exception Extractor

Transforms Loki stream values into `IncidentEvent` objects compatible with
the existing ingestion pipeline:

```python
def extract_exceptions(streams: list[LokiStream]) -> list[IncidentEvent]:
    ...
```

Extraction logic:
1. Parse log line as JSON if `loki_log_format = "json"`.
2. Extract `exception_type`, `exception_message`, `stack_trace` from known
   field names (configurable: `loki_exception_type_field`, etc.).
3. For unstructured logs: use regex to detect `Exception:` / `Error:` patterns
   and extract the traceback lines following.
4. Detect `exception_source` using the same heuristic as Phase 29/30.
5. Generate a deterministic `fingerprint` (same algorithm as Azure Monitor connector).

---

## `LokiIngestionRunner`

Follows the same interface as the existing `AzureMonitorIngestionRunner`:

```python
class LokiIngestionRunner:
    async def run_once(self) -> IngestionResult: ...
```

The `runner_factory.py` returns the correct runner based on:
```python
settings.log_source  # "azure_monitor" | "loki"
```

---

## New Settings (`packages/config/settings.py`)

```python
log_source: str = "azure_monitor"         # "azure_monitor" | "loki"
loki_base_url: str = ""
loki_app_name_pattern: str = ".*"         # LogQL label selector regex
loki_log_format: str = "json"             # "json" | "text"
loki_exception_type_field: str = "exception_type"
loki_exception_message_field: str = "exception_message"
loki_stack_trace_field: str = "stack_trace"
loki_username: str = ""                   # For basic auth
loki_api_key: str = ""                    # From Key Vault
loki_poll_interval_seconds: int = 300     # 5 minutes
```

---

## Unit Test Requirements

### `test_loki_client.py`

| Test | Asserts |
|---|---|
| `test_query_range_builds_correct_url` | URL includes correct query params |
| `test_pagination_handled` | Multiple pages fetched when `limit` reached |
| `test_auth_header_set` | Authorization header present on requests |
| `test_empty_response_returns_empty_list` | No error on empty stream |

### `test_loki_exception_extractor.py`

| Test | Asserts |
|---|---|
| `test_json_log_extracts_exception_fields` | Correct `exception_type`, `message`, `stack_trace` |
| `test_text_log_detects_exception_pattern` | Regex catches `Exception:` pattern |
| `test_fingerprint_is_deterministic` | Same log line → same fingerprint |
| `test_dotnet_source_detected` | `.cs:` in stack → `exception_source == "dotnet"` |
| `test_nodejs_source_detected` | `.js:` in stack → `exception_source == "nodejs"` |

---

## Acceptance Criteria

- `ruff check .` and `mypy apps/ packages/ --strict` pass.
- All existing Azure Monitor tests continue to pass.
- `log_source = "loki"` routes to `LokiIngestionRunner` without touching the Azure Monitor path.
- Mock Loki responses are correctly parsed into `IncidentEvent` objects.
- Fingerprinting prevents duplicate incidents from repeated Loki polls.

---

## Out of Scope

- Grafana Alerting webhook receiver (push-based ingestion).
- Tempo (distributed tracing) integration.
- Loki ruler / alerting rule management.
- Datadog / Elastic log source connectors.
