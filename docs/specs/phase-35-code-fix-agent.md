# Phase 35 — Code Fix Agent

## Goal

Introduce a dedicated **Code Fix Agent** that sits between Bug Creator and PR
Agent in the approval pipeline.  It fetches the **full file content** from the
repository, calls the LLM to generate a precise code patch, and stores the
result in `IncidentState` so the PR Agent can create the branch and PR without
performing any code-generation work itself.

### Why this phase exists

Before Phase 35 the PR Agent combined two responsibilities: (1) generate the
actual code change by calling the LLM, and (2) create the Git branch and PR.
The LLM call inside the PR Agent used a 40-line snippet (from `code_snippets`)
rather than the full file.  When the patched content was pushed to the
repository it replaced the entire file with a 40-line fragment, corrupting
every file it touched.

Phase 35 separates concerns:

- **Code Fix Agent** — owns code generation; always works from the full file.
- **PR Agent** — owns Git operations; consumes the pre-generated patch.

---

## Pipeline Position

```
bug_creator
  └─[approval_status == "approved"]─→ code_fix_agent → pr_agent → validation_agent → END
  └─[otherwise]──────────────────────────────────────────────────────────────────→ END
```

The conditional edge on `bug_creator` now routes to `code_fix_agent` instead
of `pr_agent` directly.

---

## Inputs (from IncidentState)

| Field | Type | Source |
|---|---|---|
| `approval_status` | `str \| None` | approval gate |
| `approved_recommendation_rank` | `int \| None` | approval gate |
| `recommendations` | `list[dict]` | fix_planner agent |
| `root_cause_summary` | `str \| None` | root_cause agent |
| `code_snippets` | `list[dict]` | code_context agent (for file-path hints) |

---

## Outputs (written to IncidentState)

| Field | Type | Notes |
|---|---|---|
| `code_fix_result` | `dict \| None` | `CodeFixResult` serialised; `None` when skipped |
| `agent_trace` | `list[dict]` | appended entry |
| `errors` | `list[str]` | appended on failure |

---

## Model

```python
class CodeFixResult(BaseModel):
    file_path: str           # relative path of the patched file
    original_content: str   # full file content before the fix
    patched_content: str    # full file content after the fix
    change_summary: str     # 1–2 sentence description of what changed
    confidence: float       # clamped [0, 1] — LLM self-reported confidence
    patch_applied: bool     # True when patched_content differs from original
```

---

## Agent Logic

```
1. Guard: skip if approval_status != "approved".
2. Select recommendation at approved_recommendation_rank from state.
3. Resolve file_path from recommendation["affected_files"][0].
   Fallback: use code_snippets[0]["file_path"] if affected_files is empty.
4. Fetch full file content via ADOClientProtocol.get_file_content(file_path).
   If file not found: set patch_applied=False, store CodeFixResult with
   original_content="" and a descriptive change_summary.
5. Call LLM (code_fix_v1 prompt) with:
     - exception_type, root_cause_summary
     - file_path, full original_content (up to 8 000 chars)
     - recommendation title + description + suggested_change (scrubbed)
6. Parse response → CodeFixResult.
7. Validate: patch_applied = (patched_content != original_content).
8. Write code_fix_result to state.
```

---

## Prompt

`docs/prompts/code_fix_v1.md`

The prompt instructs the LLM to return JSON:

```json
{
  "patched_content": "<complete file content after fix>",
  "change_summary": "Added null guard on line 42 before dereferencing response.",
  "confidence": 0.92
}
```

Rules enforced in the prompt:
- `patched_content` must be the complete, valid file — not a snippet.
- Apply only the minimal change described in the recommendation.
- Never remove error handling, logging, or auth checks.
- Return `patched_content` identical to `original_content` when the fix
  cannot be safely applied; explain in `change_summary`.

---

## Failure Behaviour

| Scenario | Result |
|---|---|
| `approval_status != "approved"` | Skip; `code_fix_result = None`; no error |
| SCM not configured | Skip; `code_fix_result = None`; no error |
| File not found in repo | `CodeFixResult` with `patch_applied=False`; PR Agent creates PR with manual-fix note |
| LLM call fails | `CodeFixResult` with `patch_applied=False`; error appended |
| LLM returns identical content | `patch_applied=False`; logged as `code_fix_no_change` |

---

## PR Agent Changes (Phase 19 update)

Remove `_call_llm` from `pr_agent/agent.py`.  Instead:

```python
code_fix_result = state.get("code_fix_result") or {}
original_content = code_fix_result.get("original_content", "")
patched_content  = code_fix_result.get("patched_content", "")
patch_applied    = code_fix_result.get("patch_applied", False)
file_path        = code_fix_result.get("file_path", "")
```

The PR Agent still builds the diff via `patch_builder`, creates the branch,
pushes the file, and creates the draft PR.

---

## Security Touchpoints

- **LLM call**: `scrub()` applied to `recommendation.suggested_change`,
  `recommendation.description`, and `root_cause_summary` before `json.dumps`.
  Source file content is exempt (Phase 15).
- **Agent trace**: `AgentTraceEntry` written on every execution path.
- **Credentials**: ADO PAT sourced from `pydantic-settings`; never hardcoded.

---

## Files

```
packages/agent_runtime/code_fix/
├── __init__.py
├── agent.py          — make_code_fix_node factory
└── models.py         — CodeFixResult

docs/prompts/code_fix_v1.md
tests/unit/test_code_fix_agent.py

Updated:
  packages/domain/models/agent_state.py  — add code_fix_result field
  packages/agent_runtime/pipeline.py     — insert code_fix node
  packages/agent_runtime/pr_agent/agent.py — remove _call_llm; use state
  docs/specs/phase-10-fix-planner-agent.md
  docs/specs/phase-19-pr-agent-and-approval.md
```

---

## Acceptance Criteria

- `ruff check .` and `mypy apps/ packages/ --strict` pass.
- All existing tests continue to pass.
- `code_fix_result` is `None` in state when `approval_status != "approved"`.
- `code_fix_result.patch_applied = True` when LLM returns changed content.
- `code_fix_result.patch_applied = False` when file not found or LLM unchanged.
- PR Agent no longer contains any LLM call.
- PR Agent uses `code_fix_result` from state for file content.
- Unit tests cover: approved path, skip path, file-not-found path, LLM-unchanged path.

---

## Out of Scope

- Multi-file patches (patching more than one file per recommendation).
- Syntax validation of the generated patch (Phase 36 — Validation Agent upgrade).
- GitHub source control (Phase 38).
