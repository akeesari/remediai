# Phase 07 — Root Cause Agent

## Goal

Extend the LangGraph pipeline with a **Root Cause Agent** that analyses the exception stack trace and produces a structured root-cause summary, extending `IncidentState` with `root_cause_summary` and `root_cause_json`.

---

## New Files

| Path | Purpose |
|---|---|
| `packages/agent_runtime/root_cause/__init__.py` | Package marker |
| `packages/agent_runtime/root_cause/models.py` | `RootCauseOutput`, `RootCauseJson` Pydantic models |
| `packages/agent_runtime/root_cause/stack_parser.py` | `.NET` / Python stack trace parser; filters framework internals |
| `packages/agent_runtime/root_cause/prompt.py` | Loads and caches `docs/prompts/root_cause_v1.md` |
| `packages/agent_runtime/root_cause/agent.py` | `make_root_cause_node(llm)` factory — always calls LLM |
| `tests/unit/test_stack_parser.py` | Stack frame parser unit tests |
| `tests/unit/test_root_cause_agent.py` | Root cause agent node unit tests |

## Modified Files

| Path | Change |
|---|---|
| `packages/agent_runtime/pipeline.py` | Add `root_cause` node after `triage` |
| `apps/worker/agents/runner.py` | Set status `ANALYZED` (not `TRIAGING`) on success |
| `tests/integration/test_agent_pipeline.py` | Update assertions for 2-node pipeline |
| `ROADMAP.md` | Mark Phase 7 items complete |

---

## Agent Contract

**Input fields read:** `exception_type`, `exception_message`, `stack_trace`, `triage_labels`

**Output fields set:** `root_cause_summary`, `root_cause_json`

**Prompt version:** `root_cause_v1`

**LLM always called** — there is no rule-based shortcut for root cause.

---

## Stack Frame Parser

`.NET` frame format: `   at Namespace.Class.Method(params) in File.cs:line N`

Framework-internal prefix filter (skip these):

- `System.`
- `Microsoft.AspNetCore.`
- `Microsoft.Extensions.`
- `Microsoft.EntityFrameworkCore.`
- `Microsoft.Azure.`
- `Azure.`
- `lambda_method`

Returns up to **5** user-code frames. Falls back to all frames if none pass the filter.

---

## Output Schema

```json
{
  "root_cause_summary": "Null reference in UserService.GetById when repository returns null.",
  "root_cause_json": {
    "component": "UserService.GetById",
    "likely_cause": "Missing null guard before using repository result.",
    "contributing_factors": ["No nullability test", "Unvalidated data assumption"],
    "confidence": 0.82
  },
  "evidence": ["Top frame points to UserService.GetById"]
}
```

---

## Error Handling

On LLM failure the node returns a default output with `confidence=0.0`, `likely_cause="insufficient_evidence"`, appends the error to `state.errors`, and records the error in the `agent_trace` entry. The pipeline continues.

---

## Pipeline Graph (after Phase 07)

```
triage → root_cause → END
```
