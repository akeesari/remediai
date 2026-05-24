# Phase 29 — Jira Work Item Integration

## Goal

Allow teams using Jira (instead of Azure DevOps Boards) to have RemediAI
create Jira issues from incident analyses.  The work item target is
configurable per deployment; both ADO Boards and Jira are supported
simultaneously if required.

This is a post-v1.0 extension (Milestone 9).

---

## Background

SPEC.md Non-Goals list Jira as out of MVP scope.  Milestone 9 adds this as
an optional work item backend.  The Bug Creator agent is extended to support
a pluggable `WorkItemClientProtocol` so the pipeline is not coupled to ADO.

---

## Deliverables

| Artifact | Description |
|---|---|
| `packages/integrations/jira/client.py` | `JiraClient` implementing `WorkItemClientProtocol` |
| `packages/integrations/jira/models.py` | Jira-specific request/response models |
| Updated `packages/integrations/protocols.py` | Extend `ADOBoardsClientProtocol` → `WorkItemClientProtocol` (rename + generalise) |
| Updated `packages/agent_runtime/bug_creator/agent.py` | Use `WorkItemClientProtocol`; resolve Jira or ADO client from settings |
| Updated `packages/config/settings.py` | `work_item_backend`, `jira_*` settings |
| `tests/unit/test_jira_client.py` | Unit tests with mock Jira REST API |
| Updated `tests/unit/test_bug_creator.py` | Tests for Jira path |
| `docs/runbooks/jira-setup.md` | Operator guide: Jira project setup, API token configuration |

---

## `WorkItemClientProtocol`

Rename `ADOBoardsClientProtocol` to `WorkItemClientProtocol` and generalise
the return type:

```python
class WorkItemClientProtocol(Protocol):
    async def create_work_item(
        self,
        title: str,
        description: str,
        priority: str,
        labels: list[str],
        incident_id: str,
    ) -> WorkItemResult: ...

class WorkItemResult(BaseModel):
    item_id: str            # ADO integer ID or Jira issue key (e.g., "PROJ-123")
    item_url: str
    item_type: str          # "bug" | "story" | "task"
```

The existing `AzureDevOpsBoardsClient.create_bug()` is wrapped to implement
`WorkItemClientProtocol.create_work_item()` for backwards compatibility.

---

## `JiraClient`

```python
class JiraClient:
    """Implements WorkItemClientProtocol using the Jira REST API v3."""

    def __init__(self, base_url: str, email: str, api_token: str, project_key: str): ...

    async def create_work_item(
        self,
        title: str,
        description: str,
        priority: str,
        labels: list[str],
        incident_id: str,
    ) -> WorkItemResult: ...
```

### Jira Issue Creation

`POST /rest/api/3/issue`

Request body:
```json
{
  "fields": {
    "project": { "key": "{{ project_key }}" },
    "summary": "[RemediAI] {{ title }}",
    "description": {
      "type": "doc",
      "version": 1,
      "content": [{ "type": "paragraph", "content": [{ "type": "text", "text": "{{ description }}" }] }]
    },
    "issuetype": { "name": "Bug" },
    "priority": { "name": "{{ jira_priority }}" },
    "labels": ["remediai", "{{ exception_type_label }}"]
  }
}
```

**Priority mapping** (RemediAI → Jira):

| RemediAI | Jira |
|---|---|
| `critical` | `Highest` |
| `high` | `High` |
| `medium` | `Medium` |
| `low` | `Low` |

### Authentication

Jira Cloud uses Basic Auth with email + API token (base64-encoded).
API token stored in Key Vault as `jira-api-token`.

---

## Bug Creator Agent Changes

```python
def _resolve_client(work_item_client, settings):
    if work_item_client is not None:
        return work_item_client
    s = settings or get_settings()
    backend = getattr(s, "work_item_backend", "ado")
    if backend == "jira":
        return JiraClient.from_settings(s)
    if not getattr(s, "azure_devops_org_url", ""):
        return None
    return AzureDevOpsBoardsClient.from_settings(s)
```

---

## New Settings (`packages/config/settings.py`)

```python
work_item_backend: str = "ado"          # "ado" | "jira" | "none"
jira_base_url: str = ""                 # e.g., "https://myorg.atlassian.net"
jira_email: str = ""                    # Non-secret; safe in config
jira_api_token: str = ""               # From Key Vault: jira-api-token
jira_project_key: str = ""             # e.g., "PLAT"
jira_issue_type: str = "Bug"
```

## `WorkItemOrm` Changes

The `ado_item_id` column (integer) is insufficient for Jira issue keys.
Add a new column:

```sql
ALTER TABLE work_items ADD COLUMN item_key VARCHAR(50);
```

`ado_item_id` is retained for backwards compatibility.  `item_key` stores
the canonical identifier for both backends.  Alembic migration required.

---

## Unit Test Requirements (`test_jira_client.py`)

| Test | Asserts |
|---|---|
| `test_create_issue_posts_correct_payload` | `POST /rest/api/3/issue` with correct fields |
| `test_priority_mapping_critical` | `priority.name == "Highest"` for critical incidents |
| `test_priority_mapping_low` | `priority.name == "Low"` |
| `test_returns_issue_key_and_url` | `item_id == "PROJ-42"`, `item_url` contains issue key |
| `test_auth_header_is_basic` | `Authorization: Basic ...` header present |
| `test_api_error_raises_exception` | 400 response raises `WorkItemCreationError` |

---

## Acceptance Criteria

- `ruff check .` and `mypy apps/ packages/ --strict` pass.
- All existing ADO bug creation tests continue to pass (no regression).
- `work_item_backend = "jira"` routes to `JiraClient`.
- `work_item_backend = "ado"` routes to `AzureDevOpsBoardsClient` (unchanged behaviour).
- `work_item_backend = "none"` skips bug creation (graceful no-op).
- Alembic migration adds `item_key` column without breaking existing rows.
- Jira client unit tests pass against mock HTTP responses.

---

## Out of Scope

- Jira Service Management (JSM) specific features.
- Jira Software sprint / board assignment.
- Bidirectional sync (Jira status → RemediAI incident status).
- GitHub Issues integration.
