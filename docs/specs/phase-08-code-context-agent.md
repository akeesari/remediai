# Phase 08 — Code Context Agent

## Goal

Add a **Code Context Agent** as the third node in the LangGraph pipeline. It parses user-code stack frames (language-agnostic, reusing the multi-language parser from Phase 7), fetches the relevant source lines from the configured source control provider (Azure DevOps Repos for MVP; GitHub Phase 38+), and stores up to five `CodeSnippet` records in `IncidentState`. No LLM is required.

> **Language scope:** Frame parsing and internal-prefix filtering are language-aware. Source file fetching works for any language since it is purely path-based. The agent handles `.cs`, `.py`, `.js`, `.ts`, `.java`, and any other text file without special-casing.

---

## New Files

| Path | Purpose |
|---|---|
| `packages/integrations/azure_devops/__init__.py` | Package marker |
| `packages/integrations/azure_devops/client.py` | Async ADO Repos client (httpx + PAT auth) |
| `packages/agent_runtime/code_context/__init__.py` | Package marker |
| `packages/agent_runtime/code_context/models.py` | `CodeSnippet` Pydantic model |
| `packages/agent_runtime/code_context/agent.py` | `make_code_context_node(ado_client)` factory |
| `tests/unit/test_code_context_agent.py` | Agent node unit tests (mocked ADO client) |

## Modified Files

| Path | Change |
|---|---|
| `apps/api/core/config.py` | Add `azure_devops_repository`, `azure_devops_branch` |
| `packages/agent_runtime/pipeline.py` | Add `code_context` node; expose `ado_client` parameter |
| `tests/integration/test_agent_pipeline.py` | Inject mock ADO client; assert `code_snippets` in state |
| `ROADMAP.md` | Code Context Agent marked complete |

---

## Agent Contract

**Input fields read:** `stack_trace`, `root_cause_json`

**Output fields set:** `code_snippets` — list of `CodeSnippet` dicts

**No LLM call.** The node is purely I/O: parse → fetch → slice.

---

## Frame Selection Logic

1. Run `parse_stack_frames(stack_trace)` from Phase 7.
2. Keep only frames where `is_user_code is True` AND `file_path is not None` AND `line_number is not None`.
3. Take the first 5 qualifying frames.

---

## Snippet Extraction

For each qualifying frame:
- Call `ado_client.get_file_content(file_path)` — returns raw text or `None` (404).
- If `None`, skip silently.
- Split content by lines; extract window: `max(1, line - 20)` … `min(total, line + 20)` (1-indexed).
- Record `repo`, `commit_sha` (fetched once from ADO at node start), `start_line`, `end_line`.

---

## CodeSnippet Schema

```python
class CodeSnippet(BaseModel):
    file_path: str
    start_line: int
    end_line: int
    content: str
    repo: str
    commit_sha: str
```

---

## ADO Client Auth

Basic authentication: empty username, PAT as password (`httpx.BasicAuth("", pat)`).

REST endpoint for file content:
```
GET {org_url}/{project}/_apis/git/repositories/{repo}/items
    ?path={file_path}
    &versionDescriptor.version={branch}
    &versionDescriptor.versionType=branch
    &$format=text
    &api-version=7.1
```

---

## Pipeline Graph (after Phase 08)

```
triage → root_cause → code_context → END
```
