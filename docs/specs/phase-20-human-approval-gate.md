# Phase 20 — Human Approval Gate

## Goal

Give engineers an explicit in-dashboard action to approve a fix recommendation
before the PR Agent runs.  No automated PR creation may occur without a
recorded approval event in the database.

---

## Background

SECURITY_GUARDRAILS.md principle 1: "Humans approve all code changes."
AGENT_DESIGN.md §7 states the PR Agent "requires an explicit human approval
event stored in the database before the PR Agent runs."

This phase adds:
1. A database column to track approval state per incident.
2. A FastAPI endpoint that records the approval.
3. A React dashboard action button on the incident detail page.

---

## Deliverables

| Artifact | Description |
|---|---|
| Alembic migration | Add `approval_status`, `approved_by`, `approved_at`, `approved_recommendation_rank` to `incidents` table |
| Updated `packages/data_access/models/incident_orm.py` | New columns on `IncidentOrm` |
| `apps/api/routers/approvals.py` | `POST /api/v1/incidents/{id}/approve` and `POST /api/v1/incidents/{id}/reject` |
| `apps/api/schemas/approval.py` | Request and response Pydantic models |
| Updated `apps/api/main.py` | Register approvals router |
| Updated `apps/dashboard/src/pages/IncidentDetail.tsx` | Approve / Reject buttons on recommendation card |
| `apps/dashboard/src/api/approvals.ts` | `approveIncident()`, `rejectIncident()` API calls |
| `tests/unit/test_approvals_router.py` | Unit tests for approval endpoints |
| Alembic migration file | `alembic/versions/XXXX_add_approval_fields.py` |

---

## Database Changes

### New columns on `incidents` table

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `approval_status` | `VARCHAR(20)` | yes | `NULL` | `NULL \| approved \| rejected` |
| `approved_by` | `VARCHAR(255)` | yes | `NULL` | Identity of the approving engineer |
| `approved_at` | `TIMESTAMPTZ` | yes | `NULL` | When the approval was recorded |
| `approved_recommendation_rank` | `INTEGER` | yes | `NULL` | Which recommendation was approved |

`approval_status` is `NULL` until an explicit approve/reject action is taken.
A rejected incident can be re-approved (overwrites previous state).

---

## API Endpoints

### `POST /api/v1/incidents/{id}/approve`

**Request body:**
```json
{
  "recommendation_rank": 1,
  "approved_by": "engineer@contoso.com"
}
```

**Response `200`:**
```json
{
  "incident_id": "...",
  "approval_status": "approved",
  "approved_recommendation_rank": 1,
  "approved_by": "engineer@contoso.com",
  "approved_at": "2026-05-24T10:00:00Z"
}
```

**Errors:**
- `404` — incident not found.
- `409` — incident not in `analyzed` status (can only approve analyzed incidents).
- `422` — `recommendation_rank` out of range for this incident's recommendations.

### `POST /api/v1/incidents/{id}/reject`

**Request body:**
```json
{
  "rejected_by": "engineer@contoso.com",
  "reason": "Recommendation does not match our coding standards."
}
```

**Response `200`:**
```json
{
  "incident_id": "...",
  "approval_status": "rejected"
}
```

Rejection reason is stored in `agent_trace` as an audit entry (not a separate column).

---

## `IncidentDetail` API Response Update

Add to `IncidentDetail` schema:
```python
approval_status: str | None = None
approved_recommendation_rank: int | None = None
approved_at: datetime | None = None
```

---

## Dashboard UI Changes

On `IncidentDetail.tsx`, add an **Approval Panel** below the Recommendations
section, visible only when `status == "analyzed"` and `approval_status` is
`null` or `"rejected"`:

```
┌─────────────────────────────────────────────────┐
│  Create Pull Request                            │
│                                                 │
│  Select recommendation to apply:               │
│  ○ #1 Add retry with exponential back-off      │
│  ○ #2 Add null guard on gateway response       │
│                                                 │
│  [Approve & Queue PR]   [Reject All]           │
└─────────────────────────────────────────────────┘
```

- Selecting a recommendation and clicking **Approve & Queue PR** calls
  `POST /api/v1/incidents/{id}/approve`.
- On success, the panel is replaced with a status badge: "PR Queued —
  approved by {approved_by} at {approved_at}".
- **Reject All** calls `POST /api/v1/incidents/{id}/reject` and shows a
  "Rejected" badge.
- When `approval_status == "approved"` and `pr_url` is set, show a link
  to the ADO PR.

---

## Audit Trail

On each approve/reject call, append an entry to the incident's `agent_trace`
column:
```json
{
  "agent_name": "human_approval",
  "input_summary": "recommendation_rank=1",
  "output_summary": "status=approved, by=engineer@contoso.com",
  "latency_ms": 0,
  "error": null
}
```

---

## Unit Test Requirements (`test_approvals_router.py`)

| Test | Asserts |
|---|---|
| `test_approve_analyzed_incident` | Returns 200; `approval_status == "approved"` in DB |
| `test_approve_non_analyzed_returns_409` | Returns 409 for `status == "new"` incident |
| `test_approve_invalid_rank_returns_422` | Returns 422 when rank out of range |
| `test_reject_incident` | Returns 200; `approval_status == "rejected"` in DB |
| `test_re_approve_after_reject` | Overwrites rejected state; returns 200 |
| `test_approve_unknown_incident_returns_404` | Returns 404 |

---

## Acceptance Criteria

- Alembic migration runs cleanly (`alembic upgrade head`).
- `ruff check .` and `mypy apps/ packages/ --strict` pass.
- All existing tests continue to pass.
- Approve endpoint sets `approval_status = "approved"` in the database.
- Reject endpoint sets `approval_status = "rejected"`.
- Dashboard shows Approval Panel only for analyzed incidents without active approval.
- PR Agent (Phase 19) reads `approval_status` from `IncidentState`; this phase
  ensures the field is populated before the pipeline runs.

---

## Out of Scope

- Multi-approver workflows or approval quorum rules.
- Role-based access control on the approve endpoint (future auth phase).
- Email / Slack notification on approval (future notification phase).
