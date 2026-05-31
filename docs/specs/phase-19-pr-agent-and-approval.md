# Phase 19 — PR Agent + Human Approval Gate

## Goal

Give engineers an explicit in-dashboard action to approve a fix recommendation,
then automatically create a feature branch, apply the approved change as a code
patch, and open a **draft** pull request in Azure DevOps Repos.  No PR may be
created without a recorded approval event in the database.  The PR is never
auto-completed.

These two concerns (approval gate and PR agent) were originally separate phases
but are merged here because the approval gate is the PR Agent's sole trigger
condition — neither is useful without the other.

---

## Background

SECURITY_GUARDRAILS.md principle 1: "Humans approve all code changes."
SPEC.md FR-11 and AGENT_DESIGN.md §7 define the PR Agent as a Phase 2
capability requiring an explicit human approval event stored in the database.

---

## Deliverables

### Human Approval Gate

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

### PR Agent

| Artifact | Description |
|---|---|
| `packages/agent_runtime/pr_agent/agent.py` | `make_pr_agent_node(ado_client)` factory |
| `packages/agent_runtime/pr_agent/models.py` | `PRAgentOutput` Pydantic model |
| `packages/agent_runtime/pr_agent/patch_builder.py` | `build_patch(snippet, suggested_change)` — generates a unified diff |
| `packages/integrations/ado/repos_writer.py` | `create_branch()`, `push_patch()`, `create_pull_request()` on ADO Repos |
| Updated `packages/agent_runtime/pipeline.py` | Wire PR Agent after Bug Creator (conditional edge on `approval_status`) |
| Updated `packages/domain/models/agent_state.py` | Add `pr_branch`, `pr_url`, `approval_status` fields to `IncidentState` |
| `tests/unit/test_pr_agent.py` | Unit tests for node + patch builder |
| `tests/unit/test_repos_writer.py` | Unit tests for ADO Repos writer with mock HTTP |
| `docs/prompts/pr_patch_v1.md` | Prompt: refine `suggested_change` into a valid unified diff |

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

**Errors:** `404` incident not found · `409` incident not in `analyzed` status ·
`422` `recommendation_rank` out of range.

### `POST /api/v1/incidents/{id}/reject`

**Request body:**
```json
{
  "rejected_by": "engineer@contoso.com",
  "reason": "Recommendation does not match our coding standards."
}
```

Rejection reason is stored in `agent_trace` as an audit entry.

---

## Dashboard UI — Approval Panel

On `IncidentDetail.tsx`, below Recommendations, visible only when
`status == "analyzed"` and `approval_status` is `null` or `"rejected"`:

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

On approval, panel is replaced with: "PR Queued — approved by {approved_by} at
{approved_at}".  When `approval_status == "approved"` and `pr_url` is set,
show a link to the ADO draft PR.

---

## Pipeline Integration

```
bug_creator → [approval_status == "approved"] → pr_agent → END
             [approval_status != "approved"] → END
```

Incidents without approval terminate after Bug Creator (current MVP behaviour
preserved).

---

## PR Agent Logic

> **Phase 35 update:** The PR Agent no longer calls the LLM.  Code generation
> is performed by the Code Fix Agent which runs before the PR Agent and stores
> `code_fix_result` in `IncidentState`.  The PR Agent reads that result and
> focuses solely on Git operations.

```
1. Validate: approval_status == "approved"; approved_recommendation_rank set.
2. Read code_fix_result from state (set by Code Fix Agent, Phase 35).
3. Create branch: remedia/{incident_id[:8]}/{recommendation.rank}
4. If code_fix_result.patch_applied:
     Push full patched file content to branch via ADO Repos push API.
   Else:
     Skip push; PR description will include manual-review note.
5. Create draft PR:
   - Title:       [RemediAI] {recommendation.title}
   - Description: root_cause_summary + recommendation.description
                  + change_summary from code_fix_result + disclaimer
   - Draft:       true
   - Auto-complete: never set
6. Write pr_branch and pr_url to state and to WorkItemOrm in PostgreSQL.
```

---

## `PRAgentOutput` Model

```python
class PRAgentOutput(BaseModel):
    pr_branch: str
    pr_url: str
    pr_id: int
    patch_applied: bool
    files_changed: list[str]
```

---

## `IncidentState` Additions

```python
approval_status: str | None          # None | "approved" | "rejected"
approved_recommendation_rank: int | None
pr_branch: str | None
pr_url: str | None
```

---

## ADO Repos Writer

| Method | Description |
|---|---|
| `create_branch(repo, branch_name, from_ref)` | Creates a Git ref via ADO Refs API |
| `push_patch(repo, branch, file_path, content, commit_message)` | Pushes file change via ADO Push API |
| `create_pull_request(repo, source_branch, target_branch, title, description, is_draft)` | Creates PR; returns ID and URL |

Authentication: `azure_devops_pat` from `pydantic-settings`.

---

## Safety Constraints

- The PR Agent may only write to the repository in `azure_devops_repository`.
- Branch names are prefixed `remedia/` and scoped to the incident ID.
- Draft status is hardcoded — no code path sets auto-complete.
- Patch apply conflict → `patch_applied = False`, error in `state.errors`, PR
  still created with a note for the reviewer.
- Max diff size: 500 lines.  Larger diffs are rejected with an error.

---

## PII Scrubbing

The PR Agent calls an LLM (`pr_patch_v1`).  Before building `user_content`
in `_call_llm()`, apply `scrub()` to any field sourced from incident state:

```python
from packages.integrations.pii_scrubber import scrub

user_content = json.dumps({
    "file_path": recommendation.affected_files[0],
    "original_content": original_content,          # source file — exempt per Phase 15 spec
    "suggested_change": scrub(recommendation.suggested_change),
})
```

Add `log.debug("pii_scrub_applied", fields_scrubbed=["suggested_change"])`.

---

## Audit Trail

### Approval events

On each approve/reject call, append to `agent_trace`:
```json
{
  "agent_name": "human_approval",
  "input_summary": "recommendation_rank=1",
  "output_summary": "status=approved, by=engineer@contoso.com",
  "latency_ms": 0,
  "error": null
}
```

### PR Agent

The PR Agent writes an `AgentTraceEntry` to `state["agent_trace"]` following
the existing node factory pattern.

---

## Unit Test Requirements

### `test_approvals_router.py`

| Test | Asserts |
|---|---|
| `test_approve_analyzed_incident` | Returns 200; `approval_status == "approved"` in DB |
| `test_approve_non_analyzed_returns_409` | Returns 409 for `status == "new"` |
| `test_approve_invalid_rank_returns_422` | Returns 422 when rank out of range |
| `test_reject_incident` | Returns 200; `approval_status == "rejected"` in DB |
| `test_re_approve_after_reject` | Overwrites rejected state; returns 200 |
| `test_approve_unknown_incident_returns_404` | Returns 404 |

### `test_pr_agent.py`

| Test | Asserts |
|---|---|
| `test_approved_incident_creates_branch` | `create_branch` called with correct naming pattern |
| `test_approved_incident_creates_draft_pr` | PR created with `is_draft=True` |
| `test_pr_url_written_to_state` | `state["pr_url"]` non-empty after node run |
| `test_unapproved_incident_skips_pr` | Node not called when `approval_status != "approved"` |
| `test_patch_too_large_sets_error` | Error appended when diff exceeds 500 lines |

### `test_repos_writer.py`

| Test | Asserts |
|---|---|
| `test_create_branch_calls_correct_endpoint` | PUT to `/refs` with correct ref name |
| `test_push_patch_calls_push_api` | POST to `/pushes` with file content |
| `test_create_pull_request_draft` | `isDraft: true` in request payload |

---

## Acceptance Criteria

- Alembic migration runs cleanly (`alembic upgrade head`).
- `ruff check .` and `mypy apps/ packages/ --strict` pass.
- All existing tests continue to pass.
- Approve endpoint sets `approval_status = "approved"` in the database.
- Reject endpoint sets `approval_status = "rejected"`.
- Dashboard shows Approval Panel only for analyzed incidents without active approval.
- Incidents without approval skip the PR Agent (pipeline regression test).
- Incidents with `approval_status = "approved"` trigger branch + PR creation.
- PRs are never set to auto-complete in any code path.

---

## Out of Scope

- Multi-approver workflows or approval quorum rules.
- Role-based access control on the approve endpoint (future auth phase).
- Email / Slack notification on approval.
