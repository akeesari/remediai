# Phase 27 — Python Exception Support + Grafana/Loki Connector

## Goal

Extend the ingestion and triage pipeline to handle Python application
tracebacks, and add a Grafana/Loki ingestion connector so teams using the
Loki stack (instead of Azure Monitor) can use RemediAI without migrating
their observability infrastructure.

These are merged here because both add a new ingestion source type and both
follow the same extension pattern established in Phase 28 (Node.js).  They can
be implemented in parallel by two developers and merged in one commit.

---

## Background

Phase 28 established the `exception_source` heuristic and parser registry
pattern.  Python support extends it; Loki adds a second ingestion connector
alongside the Azure Monitor path introduced in Phase 4.

Both are post-v1.0 (Milestone 9) and out of MVP scope.

---

## Deliverables

### Python Exception Support

| Artifact | Description |
|---|---|
| `packages/parsers/python_stack_parser.py` | Parse Python traceback format into `StackFrame` list |
| Updated `packages/parsers/parser_registry.py` | Add `"python"` case |
| Updated `packages/domain/models/agent_state.py` | `exception_source` supports `"python"` |
| Updated `packages/agent_runtime/triage/rules.py` | Python-specific triage rules |
| `docs/prompts/triage_v4.md` | Triage prompt aware of Python; updated label taxonomy |
| `docs/prompts/root_cause_v4.md` | Root cause prompt adapted for Python traceback format |
| `tests/unit/test_python_parser.py` | Unit tests: parse real Python tracebacks |
| Updated `tests/unit/test_triage_rules.py` | Python rule coverage |
| Updated agent eval fixtures | `python_key_error.json`, `python_attribute_error.json` |

### Grafana/Loki Connector

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

## Python Traceback Format

```
Traceback (most recent call last):
  File "/app/services/order_service.py", line 88, in checkout
    user = self.user_repo.get(order.user_id)
  File "/app/repositories/user_repository.py", line 42, in get
    return self.db.query(User).filter(User.id == user_id).one()
sqlalchemy.orm.exc.NoResultFound: No row was found when one was required
```

Key differences from .NET and Node.js:
- Stack unwinds **bottom-up** (last line = innermost frame).
- Frame format: `File "{path}", line {n}, in {function}`.
- Exception type and message appear on the **last line**, not the first.
- Exception type may include a module prefix: `sqlalchemy.orm.exc.NoResultFound`.
- Multi-exception chains: `During handling of the above exception, another exception occurred:`.

---

## Python Stack Parser

1. Detect traceback header (`"Traceback (most recent call last):"`).
2. Extract frames in order (preserve bottom-up).
3. Identify `exception_type` from the final line before the message.
4. Handle chained exceptions (`__cause__` / `__context__` chains).
5. Mark `site-packages/` frames as `is_framework = True`.

---

## `exception_source` Detection Update

```python
def detect_exception_source(payload: dict) -> str:
    stack = payload.get("stack_trace", "") or ""
    if "Traceback (most recent call last)" in stack:
        return "python"
    if "at " in stack and ("node_modules" in stack or ".js:" in stack):
        return "nodejs"
    return "dotnet"
```

---

## Python Triage Rules

| Exception Type / Pattern | Priority | Labels |
|---|---|---|
| `AttributeError: 'NoneType' object has no attribute` | high | `null-reference`, `python` |
| `KeyError` | medium | `key-not-found`, `python` |
| `IndexError` | medium | `index-out-of-bounds`, `python` |
| `MemoryError` | critical | `resource-exhaustion`, `python` |
| `RecursionError` | high | `stack-overflow`, `python` |
| `ConnectionRefusedError` | medium | `connection-failure`, `python` |
| `TimeoutError` | medium | `timeout`, `python` |
| `sqlalchemy.orm.exc.NoResultFound` | medium | `not-found`, `python`, `database` |
| `django.core.exceptions.ObjectDoesNotExist` | medium | `not-found`, `python`, `django` |
| `jwt.exceptions.InvalidTokenError` | medium | `authentication`, `python` |

---

## Loki HTTP API

- **Base URL**: configurable via `loki_base_url` setting.
- **Query endpoint**: `GET /loki/api/v1/query_range`
- **Auth**: Basic auth (username + API key from Key Vault) or bearer token.
- **Pagination**: `limit` + `start`/`end` timestamps.

---

## LogQL Query Strategy

For text logs:
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

class LokiStream(BaseModel):
    labels: dict[str, str]
    values: list[tuple[str, str]]  # (nanosecond timestamp, log line)
```

---

## Exception Extractor

```python
def extract_exceptions(streams: list[LokiStream]) -> list[IncidentEvent]: ...
```

1. Parse log line as JSON if `loki_log_format = "json"`.
2. Extract `exception_type`, `exception_message`, `stack_trace` from configurable field names.
3. For unstructured logs: regex to detect `Exception:` / `Error:` patterns.
4. Detect `exception_source` using the heuristic above.
5. Generate a deterministic `fingerprint` (same algorithm as Azure Monitor connector).

---

## `LokiIngestionRunner`

```python
class LokiIngestionRunner:
    async def run_once(self) -> IngestionResult: ...
```

`runner_factory.py` returns the correct runner:
```python
settings.log_source  # "azure_monitor" | "loki"
```

---

## New Settings (`packages/config/settings.py`)

```python
log_source: str = "azure_monitor"
loki_base_url: str = ""
loki_app_name_pattern: str = ".*"
loki_log_format: str = "json"             # "json" | "text"
loki_exception_type_field: str = "exception_type"
loki_exception_message_field: str = "exception_message"
loki_stack_trace_field: str = "stack_trace"
loki_username: str = ""
loki_api_key: str = ""                    # From Key Vault: loki-api-key
loki_poll_interval_seconds: int = 300
```

`loki_api_key` is a Key Vault secret — do not commit a real value.

---

## Agent Eval Fixtures

### `python_key_error.json`

```json
{
  "incident_id": "eval-python-001",
  "exception_source": "python",
  "exception_type": "KeyError",
  "exception_message": "'user_id'",
  "stack_trace": "Traceback (most recent call last):\n  File \"/app/services/order_service.py\", line 88, in checkout\n    user = session['user_id']\nKeyError: 'user_id'",
  "expected": {
    "priority": "medium",
    "triage_labels_contains": ["key-not-found", "python"],
    "triage_rule_matched": true
  }
}
```

### `python_attribute_error.json`

```json
{
  "incident_id": "eval-python-002",
  "exception_source": "python",
  "exception_type": "AttributeError",
  "exception_message": "'NoneType' object has no attribute 'email'",
  "stack_trace": "Traceback (most recent call last):\n  File \"/app/api/views.py\", line 34, in get_user\n    return user.email\nAttributeError: 'NoneType' object has no attribute 'email'",
  "expected": {
    "priority": "high",
    "triage_labels_contains": ["null-reference", "python"],
    "triage_rule_matched": true
  }
}
```

---

## Unit Test Requirements

### `test_python_parser.py`

- Simple traceback: correct exception type, message, frame list.
- Chained exception: outer exception type used; inner preserved in context.
- Framework-only frames: all marked `is_framework = True`.
- Multi-line exception message: captured without truncation.

### `test_loki_client.py`

| Test | Asserts |
|---|---|
| `test_query_range_builds_correct_url` | URL includes correct query params |
| `test_pagination_handled` | Multiple pages fetched when `limit` reached |
| `test_auth_header_set` | Authorization header present |
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
- Python traceback fixtures produce correct priority and labels.
- `site-packages/` frames are marked `is_framework = True`.
- Chained exceptions parsed without error.
- Existing .NET and Node.js tests continue to pass.
- `log_source = "loki"` routes to `LokiIngestionRunner` without touching the Azure Monitor path.
- Mock Loki responses are correctly parsed into `IncidentEvent` objects.
- Fingerprinting prevents duplicate incidents from repeated Loki polls.
- All existing Azure Monitor tests continue to pass.

---

## Out of Scope

- Celery task traceback format; asyncio task exception wrappers.
- Python source code context via ADO Repos (code context agent already handles arbitrary paths).
- Grafana Alerting webhook receiver (push-based ingestion).
- Tempo (distributed tracing) integration.
- Datadog / Elastic log source connectors.
