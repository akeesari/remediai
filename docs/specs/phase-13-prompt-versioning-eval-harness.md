# Phase 13 — Prompt Versioning + Agent Eval Harness

## Goal

Centralise all LLM prompt management behind a versioned registry and add an
end-to-end eval harness that exercises the full 6-node agent pipeline against
representative incident fixtures, without any real Azure credentials.

---

## Deliverables

| Artifact | Description |
|---|---|
| `packages/agent_runtime/prompt_registry.py` | Central `PromptRegistry` class; singleton accessor `get_registry()` |
| `packages/agent_runtime/triage/prompt.py` | Updated to delegate to registry |
| `packages/agent_runtime/root_cause/prompt.py` | Updated to delegate to registry |
| `packages/agent_runtime/fix_planner/agent.py` | `_load_prompt()` updated to use registry |
| `tests/agent-evals/fixtures/null_reference.json` | Fixture: `System.NullReferenceException` |
| `tests/agent-evals/fixtures/out_of_memory.json` | Fixture: `System.OutOfMemoryException` |
| `tests/agent-evals/fixtures/unknown_exception.json` | Fixture: unknown `PaymentGatewayException` |
| `tests/agent-evals/test_agent_evals.py` | 17 eval tests across 4 test classes |

---

## PromptRegistry Design

```
docs/prompts/
  triage_v1.md
  root_cause_v1.md
  fix_planner_v1.md
```

- `PromptRegistry.load(name, version)` reads `{name}_v{version}.md`, caches in memory.
- `available_versions(name)` returns sorted list of version strings present on disk.
- `clear_cache()` resets the in-process cache (used in tests).
- `get_registry()` returns a module-level singleton (lazily constructed).

All three agents (`triage`, `root_cause`, `fix_planner`) delegate through
`get_registry().load(name, "1")` — no agent carries its own Path logic.

---

## Eval Harness Design

### Fixtures

Each fixture JSON defines both input state fields and an `expected` block:

```json
{
  "incident_id": "...",
  "exception_type": "...",
  "expected": {
    "priority": "high",
    "triage_labels_contains": ["null-reference"],
    "triage_rule_matched": true,
    "trace_agent_names": ["triage", "root_cause", "code_context", "rag", "fix_planner", "bug_creator"],
    "llm_call_count": 2
  }
}
```

### Mock strategy

| Client | Mock | Return value |
|---|---|---|
| LLM | `AsyncMock(side_effect=[...AIMessage...])` | Canned JSON for each node |
| ADO Repos | `AsyncMock` | `None` file content, `"abc123"` SHA |
| Azure AI Search | `AsyncMock` | `[]` results |
| ADO Boards | `AsyncMock` | `{"id": N, "_links": {"html": {"href": "..."}}}` |

**Rule path** (NullReference, OOM): 2 LLM calls — `root_cause` + `fix_planner`.
Triage is handled by deterministic rules, so no LLM call is made.

**LLM path** (unknown exception): 3 LLM calls — `triage` + `root_cause` + `fix_planner`.

### Test classes

| Class | Fixture | Tests |
|---|---|---|
| `TestNullReferenceFixture` | `null_reference.json` | priority, labels, trace, no errors, rule-path LLM count |
| `TestOutOfMemoryFixture` | `out_of_memory.json` | priority, root cause + recs present, bug ID returned |
| `TestUnknownExceptionFixture` | `unknown_exception.json` | LLM call count, full trace, root cause + recs |
| `TestPromptRegistry` | (no fixture) | load, cache, versions, clear |

---

## Acceptance Criteria

- `ruff check .` passes with no warnings.
- `mypy apps/ packages/ --strict` passes with no issues.
- All 17 eval tests pass.
- Registry singleton returns the same object on repeated `load()` calls (cache test).
- Unknown exception triggers 3 LLM calls; rule-matched exception triggers 2.
