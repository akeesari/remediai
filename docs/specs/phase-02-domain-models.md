# Phase 2 — Domain Models

## Objective

Define all core Pydantic v2 domain models in `packages/domain/`. These models are the
single source of truth for data shapes across the API, worker, agent pipeline, and database
layers. Every subsequent phase imports from here — nothing defines its own data structures.

After this phase, all models import cleanly, `mypy --strict` passes, and unit tests
validate construction, defaults, enums, fingerprint generation, and serialisation.

## Milestone

`ROADMAP.md` — Milestone 1: Foundation
Check off: `Domain models defined (Pydantic)`

---

## Files to Create

```
packages/domain/models/__init__.py
packages/domain/models/incident.py       — Incident, IncidentStatus, IncidentPriority
packages/domain/models/analysis.py       — CodeSnippet, RAGResult, RootCauseJson,
                                            Recommendation, IncidentAnalysis
packages/domain/models/work_item.py      — WorkItem, WorkItemType
packages/domain/models/audit.py          — AuditLog, AgentTraceEntry
packages/domain/models/agent_state.py    — IncidentState (TypedDict)
packages/domain/exceptions.py            — DomainError, IncidentNotFoundError,
                                            DuplicateIncidentError
```

Update:
```
packages/domain/__init__.py              — re-export all public symbols
```

Tests:
```
tests/unit/test_domain_incident.py
tests/unit/test_domain_analysis.py
tests/unit/test_domain_agent_state.py
```

---

## Model Specifications

### `IncidentPriority` / `IncidentStatus`  (`incident.py`)

```python
class IncidentPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class IncidentStatus(str, Enum):
    NEW = "new"
    TRIAGING = "triaging"
    ANALYZED = "analyzed"
    BUG_CREATED = "bug_created"
    RESOLVED = "resolved"
    ANALYSIS_FAILED = "analysis_failed"
```

### `Incident`  (`incident.py`)

| Field | Type | Default |
|---|---|---|
| `id` | `UUID` | `uuid4()` |
| `correlation_id` | `UUID` | `uuid4()` |
| `source` | `str` | required |
| `exception_type` | `str` | required |
| `exception_message` | `str` | required |
| `stack_trace` | `str \| None` | `None` |
| `fingerprint` | `str` | computed — see below |
| `priority` | `IncidentPriority` | `MEDIUM` |
| `status` | `IncidentStatus` | `NEW` |
| `raw_payload` | `dict[str, Any]` | `{}` |
| `created_at` | `datetime` | `datetime.now(UTC)` |
| `updated_at` | `datetime` | `datetime.now(UTC)` |

`fingerprint` is a SHA-256 hex digest of
`f"{exception_type}:{exception_message[:200]}"`.
Computed via `@model_validator(mode="before")` — if not supplied, derive it.

### `CodeSnippet`  (`analysis.py`)

| Field | Type |
|---|---|
| `file_path` | `str` |
| `start_line` | `int` |
| `end_line` | `int` |
| `content` | `str` |
| `repo` | `str` |
| `commit_sha` | `str` |

### `RAGResult`  (`analysis.py`)

| Field | Type | Default |
|---|---|---|
| `source` | `str` | required |
| `title` | `str` | required |
| `excerpt` | `str` | required |
| `relevance_score` | `float` | required |
| `url` | `str \| None` | `None` |

### `RootCauseJson`  (`analysis.py`)

| Field | Type |
|---|---|
| `component` | `str` |
| `likely_cause` | `str` |
| `contributing_factors` | `list[str]` |
| `confidence` | `float` |

### `Recommendation`  (`analysis.py`)

| Field | Type | Default |
|---|---|---|
| `rank` | `int` | required |
| `title` | `str` | required |
| `description` | `str` | required |
| `affected_files` | `list[str]` | required |
| `suggested_change` | `str` | required |
| `confidence` | `float` | required |
| `source_refs` | `list[str]` | `[]` |

### `IncidentAnalysis`  (`analysis.py`)

| Field | Type | Default |
|---|---|---|
| `id` | `UUID` | `uuid4()` |
| `incident_id` | `UUID` | required |
| `root_cause` | `str \| None` | `None` |
| `root_cause_json` | `RootCauseJson \| None` | `None` |
| `recommendations` | `list[Recommendation]` | `[]` |
| `code_snippets` | `list[CodeSnippet]` | `[]` |
| `rag_results` | `list[RAGResult]` | `[]` |
| `agent_trace` | `list[AgentTraceEntry]` | `[]` |
| `created_at` | `datetime` | `datetime.now(UTC)` |

### `WorkItemType` / `WorkItem`  (`work_item.py`)

```python
class WorkItemType(str, Enum):
    BUG = "bug"
    TASK = "task"
```

| Field | Type | Default |
|---|---|---|
| `id` | `UUID` | `uuid4()` |
| `incident_id` | `UUID` | required |
| `ado_item_id` | `int` | required |
| `ado_item_url` | `str` | required |
| `item_type` | `WorkItemType` | `BUG` |
| `created_at` | `datetime` | `datetime.now(UTC)` |

### `AgentTraceEntry`  (`audit.py`)

| Field | Type | Default |
|---|---|---|
| `agent_name` | `str` | required |
| `prompt_version` | `str \| None` | `None` |
| `input_summary` | `str` | required |
| `output_summary` | `str` | required |
| `llm_model` | `str \| None` | `None` |
| `tokens_used` | `int \| None` | `None` |
| `latency_ms` | `int` | required |
| `timestamp` | `datetime` | `datetime.now(UTC)` |
| `error` | `str \| None` | `None` |

### `AuditLog`  (`audit.py`)

| Field | Type | Default |
|---|---|---|
| `id` | `UUID` | `uuid4()` |
| `incident_id` | `UUID \| None` | `None` |
| `agent_name` | `str` | required |
| `action` | `str` | required |
| `input_summary` | `str \| None` | `None` |
| `output_summary` | `str \| None` | `None` |
| `actor_identity` | `str \| None` | `None` |
| `metadata` | `dict[str, Any]` | `{}` |
| `created_at` | `datetime` | `datetime.now(UTC)` |

### `IncidentState`  (`agent_state.py`)

`TypedDict` used as the LangGraph graph state. All fields optional where the
agent pipeline fills them in progressively.

```python
class IncidentState(TypedDict):
    # Core incident (required at pipeline entry)
    incident_id: str
    correlation_id: str
    exception_type: str
    exception_message: str
    stack_trace: str
    raw_payload: dict[str, Any]
    # Triage outputs
    priority: str | None
    triage_labels: list[str]
    group_id: str | None
    # Root cause outputs
    root_cause_summary: str | None
    root_cause_json: dict[str, Any] | None
    # Code context outputs
    code_snippets: list[dict[str, Any]]
    # RAG outputs
    rag_results: list[dict[str, Any]]
    # Fix planner outputs
    recommendations: list[dict[str, Any]]
    # Bug creation outputs
    ado_bug_id: int | None
    ado_bug_url: str | None
    # Phase 2
    pr_branch: str | None
    pr_url: str | None
    validation_report: dict[str, Any] | None
    # Audit
    agent_trace: list[dict[str, Any]]
    errors: list[str]
```

Use `dict[str, Any]` for nested model fields (not the Pydantic models directly)
to keep the state JSON-serialisable for LangGraph checkpointing.

### `packages/domain/exceptions.py`

```python
class DomainError(Exception): ...
class IncidentNotFoundError(DomainError): ...
class DuplicateIncidentError(DomainError): ...
```

---

## Acceptance Criteria

- [ ] `python -c "from packages.domain import Incident, IncidentAnalysis, WorkItem, AuditLog, IncidentState; print('OK')"` prints `OK`
- [ ] `pytest tests/unit/test_domain_incident.py tests/unit/test_domain_analysis.py tests/unit/test_domain_agent_state.py -v` — all tests pass
- [ ] `ruff check packages/domain/` — 0 violations
- [ ] `mypy packages/domain/ --strict` — 0 errors

---

## Commit Message

```
feat(domain): add core Pydantic domain models and LangGraph agent state

- Incident with auto-fingerprint (SHA-256), priority/status enums
- IncidentAnalysis, CodeSnippet, RAGResult, RootCauseJson, Recommendation
- WorkItem with WorkItemType enum
- AgentTraceEntry and AuditLog for immutable audit trail
- IncidentState TypedDict for LangGraph pipeline state
- DomainError hierarchy (IncidentNotFoundError, DuplicateIncidentError)
- Unit tests covering construction, defaults, enums, fingerprint, serialisation
```
