# Phase 11 — Azure DevOps Bug Integration

## Goal

Automatically create an Azure DevOps Bug work item from the completed incident analysis. This is the sixth and final node in the analysis pipeline.

## Inputs (from IncidentState)

| Field | Type | Source |
|---|---|---|
| `exception_type` | `str` | ingestion |
| `exception_message` | `str` | ingestion |
| `priority` | `str` | triage agent |
| `triage_labels` | `list[str]` | triage agent |
| `root_cause_summary` | `str` | root_cause agent |
| `root_cause_json` | `dict` | root_cause agent |
| `recommendations` | `list[dict]` | fix_planner agent |
| `incident_id` | `str` | ingestion |

## Outputs (written to IncidentState)

| Field | Type | Notes |
|---|---|---|
| `ado_bug_id` | `int \| None` | ADO work item ID; None if skipped or failed |
| `ado_bug_url` | `str \| None` | Direct link to ADO bug; None if skipped or failed |
| `agent_trace` | `list[dict]` | appended entry with `latency_ms` |
| `errors` | `list[str]` | appended on failure |

## ADO Work Item Fields

| ADO Field | Value |
|---|---|
| `System.Title` | `[PRIORITY] ExceptionType: message[:80]` |
| `System.Description` | HTML-formatted root cause + recommendations |
| `Microsoft.VSTS.Common.Priority` | 1=critical, 2=high, 3=medium, 4=low |
| `System.Tags` | triage labels joined by `, ` |

## Skip Behaviour

When no `boards_client` is injected AND `azure_devops_org_url` is empty in settings, bug creation is silently skipped. `ado_bug_id` and `ado_bug_url` are `None`; no error is added.

This allows the pipeline to run in development/test environments without ADO credentials.

## Failure Behaviour

| Scenario | Result |
|---|---|
| ADO API raises exception | Error appended to `errors`; IDs remain `None` |
| Missing `id` in response | `KeyError` caught; error appended |

## New Client: `AzureDevOpsBoardsClient`

Separate from `AzureDevOpsClient` (Repos). Located at:
`packages/integrations/azure_devops/boards_client.py`

Uses `application/json-patch+json` content type required by ADO Work Items API.

## Pipeline Position

`triage → root_cause → code_context → rag → fix_planner → bug_creator → END`

## Files

```
packages/agent_runtime/bug_creator/
├── __init__.py
├── agent.py          — make_bug_creator_node factory; ADOBoardsClientProtocol
└── models.py         — BugCreationResult

packages/integrations/azure_devops/
└── boards_client.py  — AzureDevOpsBoardsClient

docs/specs/phase-11-ado-bug-integration.md
tests/unit/test_bug_creator_agent.py
```
