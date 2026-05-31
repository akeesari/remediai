# Phase 07 — Root Cause Agent

## Goal

Extend the LangGraph pipeline with a **Root Cause Agent** that analyses the exception stack trace and produces a structured root-cause summary, extending `IncidentState` with `root_cause_summary` and `root_cause_json`.

---

## New Files

| Path | Purpose |
|---|---|
| `packages/agent_runtime/root_cause/__init__.py` | Package marker |
| `packages/agent_runtime/root_cause/models.py` | `RootCauseOutput`, `RootCauseJson` Pydantic models |
| `packages/agent_runtime/root_cause/stack_parser.py` | Multi-language stack trace parser (.NET + Python MVP; Node.js Phase 28; Java future); filters framework internals per language |
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

**Input fields read:** `exception_type`, `exception_message`, `stack_trace`, `triage_labels`, `exception_language`

**Output fields set:** `root_cause_summary`, `root_cause_json`, `recent_commits`, `dependency_context`

**Prompt version:** `root_cause_v2`

**LLM always called** — there is no rule-based shortcut for root cause.

### Gap 3 Enhancement — Recent Commits + Dependency Context

The agent optionally accepts an `ADOClientProtocol` (same interface used by Code Context Agent).
When available it fetches two additional evidence sources before the LLM call:

1. **Recent commits** for each user-code file in the top stack frames — the last 5 commits
   per file reveal what changed recently and who changed it.
2. **Dependency files** — attempts to fetch `requirements.txt`, `pyproject.toml`,
   `package.json`, and `pom.xml` from the repo root. The content (truncated to 500 chars each)
   is included as a dependency snapshot so the LLM can spot version regressions.

Both are stored in `IncidentState` (`recent_commits`, `dependency_context`) so downstream
agents (Fix Planner, Code Fix Agent) can reference them without re-fetching.

If the ADO client is not configured, the agent falls back to stack-trace-only analysis —
existing behaviour is fully preserved.

---

## Stack Frame Parser

The parser is **language-aware**. It detects the stack trace format from the exception type and stack content, then applies the appropriate parser and framework-internal filter.

### Supported Formats

**`.NET`** (MVP):
```
   at Namespace.Class.Method(params) in File.cs:line N
```
Framework internals filtered: `System.*`, `Microsoft.AspNetCore.*`, `Microsoft.Extensions.*`, `Microsoft.EntityFrameworkCore.*`, `Microsoft.Azure.*`, `Azure.*`, `lambda_method`

**Python** (Phase 27):
```
  File "/app/src/module.py", line N, in method_name
```
Framework internals filtered: paths containing `site-packages/`, `lib/python3.*/`, `<frozen `, `importlib`

**Node.js / V8** (Phase 28):
```
    at ClassName.method (/app/src/services/file.js:N:M)
    at async handler (/app/src/routes/api.ts:N:M)
```
Framework internals filtered: paths containing `node_modules/`, `internal/`, `<anonymous>`

**Java** (Future):
```
	at com.example.services.UserService.getById(UserService.java:N)
```
Framework internals filtered: `java.*`, `javax.*`, `sun.*`, `com.sun.*`, `org.springframework.*`

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
