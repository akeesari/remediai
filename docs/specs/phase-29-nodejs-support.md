# Phase 29 — Node.js Exception Support

## Goal

Extend the ingestion and triage pipeline to handle Node.js / TypeScript
application exceptions in addition to .NET exceptions.  Node.js stack traces
have a different format; triage rules and root cause prompts must be updated
to handle both.

---

## Background

SPEC.md Non-Goals list Node.js as out of scope for MVP.  Milestone 9 expands
support.  The core pipeline (LangGraph graph, PostgreSQL schema, dashboard)
remains unchanged; only the parsers, triage rules, and prompts are extended.

---

## Deliverables

| Artifact | Description |
|---|---|
| `packages/parsers/nodejs_stack_parser.py` | Parse Node.js / V8 stack trace format into `StackFrame` list |
| `packages/parsers/parser_registry.py` | `get_parser(exception_source)` — routes to `.net` or `nodejs` parser |
| Updated `packages/domain/models/agent_state.py` | Add `exception_source: str` field (`dotnet \| nodejs \| python`) |
| Updated `packages/agent_runtime/triage/rules.py` | Node.js-specific triage rules |
| `docs/prompts/triage_v3.md` | Triage prompt aware of `exception_source`; different label taxonomy for Node.js |
| `docs/prompts/root_cause_v3.md` | Root cause prompt adapted for Node.js stack frame format |
| Updated `packages/agent_runtime/triage/agent.py` | Load `triage_v3`; pass `exception_source` to prompt |
| Updated `packages/agent_runtime/root_cause/agent.py` | Load `root_cause_v3`; use correct parser |
| `tests/unit/test_nodejs_parser.py` | Unit tests: parse real Node.js / TypeScript stack traces |
| Updated `tests/unit/test_triage_rules.py` | Node.js rule coverage |
| Updated agent eval fixtures | Add `nodejs_unhandled_rejection.json` fixture |

---

## Node.js Stack Trace Format

```
Error: Cannot read properties of undefined (reading 'userId')
    at getUserProfile (/app/src/services/UserService.js:42:18)
    at async OrderController.checkout (/app/src/controllers/OrderController.js:88:22)
    at async Layer.handle [as handle_request] (/app/node_modules/express/lib/router/layer.js:95:5)
    at async next (/app/node_modules/express/lib/router/route.js:144:13)
```

TypeScript (compiled) traces include the original `.ts` source via source maps
when `source-map-support` is loaded.  The parser must handle both compiled JS
paths and source-mapped TS paths.

---

## `StackFrame` Model (shared)

The existing `StackFrame` model is used for both .NET and Node.js frames.
The parser is responsible for mapping the different formats to the same model:

```python
class StackFrame(BaseModel):
    method: str           # "getUserProfile"
    file_path: str | None # "/app/src/services/UserService.js"
    line_number: int | None
    column_number: int | None
    is_framework: bool    # True for node_modules frames
```

---

## Parser Registry

```python
def get_parser(exception_source: str) -> StackParser:
    match exception_source:
        case "nodejs":  return NodeJsStackParser()
        case "dotnet":  return DotNetStackParser()
        case _:         return DotNetStackParser()  # default
```

---

## Triage Rules — Node.js Additions

| Exception Type / Message Pattern | Priority | Labels |
|---|---|---|
| `TypeError: Cannot read properties of undefined` | high | `null-reference`, `nodejs` |
| `TypeError: Cannot read properties of null` | high | `null-reference`, `nodejs` |
| `RangeError: Maximum call stack size exceeded` | high | `stack-overflow`, `nodejs` |
| `ENOMEM` in message | critical | `resource-exhaustion`, `nodejs` |
| `UnhandledPromiseRejection` | high | `unhandled-promise`, `nodejs` |
| `ECONNREFUSED` in message | medium | `connection-failure`, `nodejs` |
| `ETIMEDOUT` in message | medium | `timeout`, `nodejs` |
| `JsonWebTokenError` | medium | `authentication`, `nodejs` |

---

## `exception_source` Detection

The ingestion service must detect the source language from the exception payload:

```python
def detect_exception_source(payload: dict) -> str:
    stack = payload.get("stack_trace", "") or ""
    if "at " in stack and ("node_modules" in stack or ".js:" in stack or ".ts:" in stack):
        return "nodejs"
    return "dotnet"  # default
```

This heuristic is applied in the ingestion service before publishing to
Service Bus, so `exception_source` is available to all downstream agents.

---

## Agent Eval Fixture (`nodejs_unhandled_rejection.json`)

```json
{
  "incident_id": "eval-nodejs-001",
  "exception_source": "nodejs",
  "exception_type": "UnhandledPromiseRejection",
  "exception_message": "Cannot read properties of undefined (reading 'userId')",
  "stack_trace": "    at getUserProfile (/app/src/services/UserService.js:42:18)\n    at async OrderController.checkout (/app/src/controllers/OrderController.js:88:22)",
  "expected": {
    "priority": "high",
    "triage_labels_contains": ["null-reference", "nodejs"],
    "triage_rule_matched": true
  }
}
```

---

## Acceptance Criteria

- `ruff check .` and `mypy apps/ packages/ --strict` pass.
- Node.js stack trace fixture produces correct priority and labels via triage rules.
- Framework frames (`node_modules/`) are filtered by the frame selector.
- Existing .NET fixtures continue to pass unmodified.
- `test_nodejs_parser.py` covers: standard Error, TypeScript with source maps,
  anonymous arrow functions, native code frames.

---

## Out of Scope

- Node.js source map resolution from the ADO Repos code context agent
  (requires source map file retrieval — deferred).
- Deno or Bun runtime support.
- ESM module path format differences (deferred).
