# Phase 12 — FastAPI Dashboard Endpoints

## Goal

Expose incident data and monitoring target policy APIs for the React dashboard.
Core endpoints remain list, detail, and metrics, and this phase now includes
target discovery and selection contracts used by local Docker mode and future
Kubernetes mode.

## Endpoints

### `GET /api/v1/incidents`

Paginated incident list with optional filters.

**Query parameters:**

| Param | Type | Default | Constraint |
|---|---|---|---|
| `page` | int | 1 | ≥ 1 |
| `page_size` | int | 20 | 1–100 |
| `status` | str | — | optional filter |
| `priority` | str | — | optional filter |
| `date_from` | datetime | — | ISO 8601 |
| `date_to` | datetime | — | ISO 8601 |

**Response:** `PaginatedResponse[IncidentListItem]`

```json
{
  "items": [...],
  "total": 42,
  "page": 1,
  "page_size": 20,
  "pages": 3
}
```

**`IncidentListItem` fields:** `id`, `exception_type`, `exception_message`, `priority`, `status`, `created_at`, `updated_at`, `has_analysis`, `external_item_url`

---

### `GET /api/v1/incidents/{id}`

Full incident detail including analysis and work items.

**Response:** `IncidentDetail`

Includes: all list fields + `stack_trace`, `root_cause`, `root_cause_json`, `recommendations`, `code_snippets`, `rag_results`, `agent_trace`, `work_items`.

Returns **404** if incident not found.

---

### `GET /api/v1/integrations/health`

Returns resolved integration provider status for dashboard warnings and operator
visibility.

**Response:** `IntegrationsHealthResponse`

```json
{
  "llm_provider_id": "azure-openai",
  "retrieval_provider_id": "azure-ai-search",
  "scm": {
    "provider_id": "azure-devops",
    "configured": true,
    "warning": null
  },
  "ticketing": {
    "provider_id": "none",
    "configured": false,
    "warning": "External ticketing is disabled."
  },
  "warnings": [
    "External ticketing is disabled."
  ]
}
```

Auth requirement: same as existing dashboard endpoints for the active
environment. In local mode this endpoint remains accessible to the dashboard;
in non-local mode it follows the dashboard API auth policy.

---

### `GET /api/v1/metrics`

Aggregate counts for the dashboard metrics panel.

**Response:** `MetricsResponse`

```json
{
  "total_incidents": 100,
  "total_analyzed": 73,
  "by_status": [{"status": "analyzed", "count": 73}, ...],
  "by_priority": [{"priority": "high", "count": 40}, ...],
  "top_errors": [{"exception_type": "System.NullReferenceException", "count": 28}, ...]
}
```

Top errors capped at 10, ordered by count descending.

---

### `GET /api/v1/targets`

Returns persisted monitoring targets.

**Query parameters:**

| Param | Type | Default | Constraint |
|---|---|---|---|
| `environment` | str | `local` | `local` \| `kubernetes` |
| `enabled_only` | bool | `false` | optional |

**Response:** `list[MonitorTarget]`

```json
[
  {
    "id": "uuid",
    "environment": "local",
    "target_type": "container",
    "target_key": "api",
    "display_name": "api",
    "enabled": true,
    "metadata": {}
  }
]
```

### `PUT /api/v1/targets`

Bulk upsert monitoring target policy.

**Request:** `UpsertMonitorTargetsRequest`

```json
{
  "environment": "local",
  "targets": [
    {
      "target_type": "container",
      "target_key": "api",
      "display_name": "api",
      "enabled": true,
      "metadata": {}
    }
  ]
}
```

**Response:**

```json
{
  "updated": 1
}
```

### `GET /api/v1/targets/discovered`

Returns discovered runtime targets for user selection.

**Query parameters:**

| Param | Type | Default | Constraint |
|---|---|---|---|
| `environment` | str | `local` | `local` \| `kubernetes` |

**Response:** `list[DiscoveredTarget]`

`local` examples: Docker container names.
`kubernetes` examples: namespace/workload pairs.

## Implementation Notes

- All endpoints use `AsyncSession` via `Depends(get_db_session)` for DB access
- `selectinload` used for `analyses` and `work_items` relationships (avoids N+1)
- `has_analysis` derived with a secondary query on `incident_analyses.incident_id`
- B008 ruff rule suppressed globally — FastAPI's `Query`/`Depends` in defaults is idiomatic
- Target APIs are auth-protected in non-local environments and local-only when
  `LOCAL_MODE=true` unless explicit cluster auth is configured.

## Files

```
apps/api/
├── main.py                       — router registration
├── routers/
│   ├── incidents.py              — list + detail endpoints
│   ├── metrics.py                — metrics endpoint
│   ├── integrations.py           — integration health endpoint
│   └── targets.py                — monitor target APIs
└── schemas/
    ├── incident.py               — PaginatedResponse, IncidentListItem, IncidentDetail
  ├── metrics.py                — MetricsResponse, StatusCount, PriorityCount, TopError
  ├── integrations.py           — integration health response contracts
  └── targets.py                — MonitorTarget, DiscoveredTarget, Upsert request/response

docs/specs/phase-12-dashboard-endpoints.md
tests/unit/test_incidents_router.py
tests/unit/test_metrics_router.py
tests/unit/test_integrations_router.py
tests/unit/test_targets_router.py
```
