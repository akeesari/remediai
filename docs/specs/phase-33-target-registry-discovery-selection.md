# Phase 33 — Target Registry + Discovery/Selection

## Goal

Add a persisted target registry that lets users discover and explicitly choose what to monitor:

- Local mode: Docker containers
- Cluster mode: Kubernetes namespaces and workloads

Discovery is automatic. Monitoring is opt-in via persisted target policy.

---

## Deliverables

| Artifact | Description |
|---|---|
| `packages/data_access/models/monitor_target_orm.py` | SQLAlchemy model for monitoring target policy |
| `alembic/versions/*_monitor_targets.py` | Migration for `monitor_targets` table |
| `apps/api/routers/targets.py` | `GET /api/v1/targets`, `PUT /api/v1/targets`, `GET /api/v1/targets/discovered` |
| `apps/api/schemas/targets.py` | API schemas for persisted and discovered targets |
| `apps/log_bridge/target_filter.py` | Applies persisted allowlist in local mode |
| `apps/dashboard/src/pages/TargetsPage.tsx` | UI for discover/select/save targets |
| `apps/dashboard/src/api/targets.ts` | Frontend API client for target endpoints |
| `apps/dashboard/src/types/targets.ts` | TypeScript target types |
| `tests/unit/test_targets_router.py` | API contract tests |
| `tests/e2e/test_target_selection_flow.py` | Local and Kubernetes selection e2e tests |

Initial implementation slice in this phase:

- Add `monitor_targets` persistence model and migration.
- Add typed target schemas and router registration under `/api/v1/targets`.
- Add local discovery based on configured bridge container list and
	kubernetes discovery placeholders gated by configuration.
- Add dashboard Targets route, API client, and selection persistence UX.
- Keep local log bridge filtering as a follow-up sub-slice; APIs and policy
	persistence ship first.

Follow-up implementation slice in this phase:

- Enforce persisted local target allowlist in `apps/log_bridge/main.py` before
	posting exceptions to ingestion.
- Add non-local authentication guard for `/api/v1/targets*` endpoints.
- Add dashboard Targets UX controls: search, type filters, bulk enable/disable,
	and transient success/error toasts.

---

## Data Model

`monitor_targets` columns:

- `id` UUID PK
- `environment` text (`local` | `kubernetes`)
- `target_type` text (`container` | `namespace` | `workload`)
- `target_key` text unique per environment/type
- `display_name` text
- `enabled` boolean
- `metadata` JSONB
- `created_at` timestamptz
- `updated_at` timestamptz

Constraints:

1. Unique index on (`environment`, `target_type`, `target_key`).
2. Empty allowlist means no incident ingestion from discovery sources.
3. Bulk upsert is idempotent.

---

## API Contract

### `GET /api/v1/targets`

Returns persisted targets, filterable by environment and enabled state.

### `PUT /api/v1/targets`

Bulk upsert and enable/disable target policy.

### `GET /api/v1/targets/discovered`

Returns currently discovered candidates:

- local: running containers
- kubernetes: namespaces/workloads from configured cluster access

For the initial implementation slice, local discovery is sourced from
`local_log_bridge_containers` and kubernetes discovery returns an empty list
unless explicit namespace/workload discovery configuration is provided.

---

## Security Touchpoints

- New LLM call introduced? **No**.
- Agent decision written? **No new decision agents**; existing audit behavior remains unchanged.
- New credential introduced? **Yes (Kubernetes discovery auth when cluster mode enabled)** — loaded through settings + secret management.
- New HTTP endpoint introduced? **Yes** — target APIs require authentication in non-local environments.

For the follow-up slice, non-local access is explicitly guarded with an
operator-provided API token header; local mode remains open for developer flow.

---

## Acceptance Criteria

- Users can discover targets and persist selection from the dashboard.
- Local bridge ingests incidents only for enabled container targets.
- Kubernetes mode supports namespace/workload selection and persistence.
- Policy changes are auditable (who changed what and when).
- Guardrails enforce max enabled targets and per-target incident rate limits.
- `ruff`, `mypy --strict`, and tests pass including e2e target-selection flow.

Initial slice acceptance criteria:

- `/api/v1/targets` endpoints are available and return typed contracts.
- Bulk upsert on `/api/v1/targets` is idempotent by
	(`environment`, `target_type`, `target_key`).
- Dashboard can discover targets, toggle enablement, and persist selection.
- Unit tests cover router behavior for list/upsert/discovered flows.

Follow-up slice acceptance criteria:

- Local log bridge checks enabled `local/container` targets and skips ingestion
	when a container is not enabled.
- `/api/v1/targets*` returns unauthorized responses in non-local mode without
	a valid operator token.
- Targets dashboard supports filtering/search and bulk state changes before
	saving.

---

## Out of Scope

- Automated ownership inference from Git metadata.
- Cross-cluster federation in one control plane.
- Alert routing and on-call escalation policy design.
