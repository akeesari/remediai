# Phase 15 — PII Scrubbing Middleware

## Goal

Mask personally identifiable information (PII) from exception messages and
stack traces **before** any content is transmitted to Azure OpenAI.  This
satisfies the mandatory `SECURITY_GUARDRAILS.md` requirement ("PII masked
before LLM") and the SPEC.md NFR for PII handling.

---

## Background

Two pipeline agents currently pass raw `exception_message` and `stack_trace`
content directly into LLM `HumanMessage` payloads:

| Agent | File | Where scrubbing must happen |
|---|---|---|
| Triage | `packages/agent_runtime/triage/agent.py` | `_call_llm()` — before `json.dumps` |
| Root Cause | `packages/agent_runtime/root_cause/agent.py` | `_call_llm()` — before `json.dumps` |
| Fix Planner | `packages/agent_runtime/fix_planner/agent.py` | `_call_llm()` — before `json.dumps` |

Scrubbing must also be applied to `input_summary` fields written to
`AgentTraceEntry` so that no raw PII enters the audit log.

---

## Deliverables

| Artifact | Description |
|---|---|
| `packages/agent_runtime/pii_scrubber.py` | `PiiScrubber` class + `scrub()` function |
| Updated `triage/agent.py` | call `scrub()` before building `user_content` |
| Updated `root_cause/agent.py` | call `scrub()` before building `user_content` |
| Updated `fix_planner/agent.py` | call `scrub()` before building `user_content` |
| `tests/unit/test_pii_scrubber.py` | unit tests covering all PII patterns |

---

## PII Patterns to Scrub

The scrubber must detect and replace the following patterns:

| Pattern | Replacement Token | Example input | Example output |
|---|---|---|---|
| Email address | `[EMAIL]` | `user@contoso.com` | `[EMAIL]` |
| IPv4 address | `[IP]` | `10.0.0.45` | `[IP]` |
| IPv6 address | `[IP]` | `2001:db8::1` | `[IP]` |
| UUID (user-context) | `[UUID]` | `a3f1c2d4-...` | `[UUID]` |
| Azure subscription ID | `[SUBSCRIPTION_ID]` | `/subscriptions/a3f1c2d4-...` | `/subscriptions/[SUBSCRIPTION_ID]` |
| Azure SAS token | `[SAS_TOKEN]` | `?sv=2021-...&sig=...` | `[SAS_TOKEN]` |
| Credit card number | `[CC]` | `4111111111111111` | `[CC]` |
| Windows username in path | `[USERNAME]` | `C:\Users\john.doe\AppData` | `C:\Users\[USERNAME]\AppData` |
| Bearer / API token | `[TOKEN]` | `Bearer eyJhbGci...` | `Bearer [TOKEN]` |

Patterns are applied in the order listed above (most-specific first) to
avoid overlapping replacements.

---

## `PiiScrubber` Design

```python
# packages/agent_runtime/pii_scrubber.py

class PiiScrubber:
    """Applies ordered regex substitutions to mask PII in text."""

    def scrub(self, text: str) -> str:
        """Return text with all PII patterns replaced by placeholder tokens."""
        ...

    def scrub_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Recursively scrub all string values in a dict (for JSON payloads)."""
        ...


def scrub(text: str) -> str:
    """Module-level convenience wrapper using a default PiiScrubber instance."""
    ...
```

- `PiiScrubber` is stateless and thread-safe (compiled regexes as class attributes).
- `scrub_dict` handles nested dicts and lists; non-string values are passed through unchanged.
- The module-level `scrub()` uses a lazily-constructed singleton `PiiScrubber`.
- Scrubbing is applied to **string values only** — it never modifies dict keys.

---

## Integration Points

### Where to call `scrub()`

In each agent's `_call_llm()` function, apply scrubbing to the user-facing
text fields before they are serialised to JSON:

```python
from packages.agent_runtime.pii_scrubber import scrub

user_content = json.dumps(
    {
        "exception_type":    state.get("exception_type", ""),
        "exception_message": scrub(state.get("exception_message", "") or ""),
        "stack_trace":       scrub((state.get("stack_trace", "") or "")[:2000]),
        # ... other fields
    }
)
```

The `exception_type` field (a fully-qualified .NET class name) does not
require scrubbing.

### Audit log (`input_summary`)

`input_summary` strings in `AgentTraceEntry` already truncate to 100
characters.  Apply `scrub()` to the raw message string before building the
summary so no PII appears in the audit trail:

```python
safe_msg = scrub(exception_message)[:100]
input_summary = f"type={exception_type}, msg={safe_msg}"
```

---

## Scrubbing Audit Log Entry

Each scrubbing operation must be recorded in `structlog` at `DEBUG` level
(not `INFO`, to avoid log-volume inflation in production):

```python
log.debug(
    "pii_scrub_applied",
    agent=AGENT_NAME,
    incident_id=incident_id,
    fields_scrubbed=["exception_message", "stack_trace"],
)
```

The **original values are never logged**.  Only the field names that were
processed are recorded.

---

## What Is NOT Scrubbed

- `exception_type` — .NET class names contain no PII.
- `incident_id`, `correlation_id` — system-generated UUIDs, not user UUIDs.
- Code snippets retrieved from Azure DevOps Repos — these are source files,
  not runtime data; their content is controlled by the engineering team.
- RAG results — same rationale as code snippets.
- `root_cause_json`, `recommendations` — generated by the LLM after scrubbing
  has already been applied; these never contain original PII.

---

## Unit Test Requirements

`tests/unit/test_pii_scrubber.py` must cover:

| Test | Input | Expected output contains |
|---|---|---|
| Email replaced | `"Contact user@example.com"` | `[EMAIL]` |
| IPv4 replaced | `"Server at 192.168.1.100"` | `[IP]` |
| IPv6 replaced | `"addr 2001:db8::1 failed"` | `[IP]` |
| UUID replaced | `"user id a3f1c2d4-1234-..."` | `[UUID]` |
| Azure subscription replaced | `"/subscriptions/a3f1c2d4-..."` | `[SUBSCRIPTION_ID]` |
| SAS token replaced | `"?sv=2021-06-08&sig=abc123"` | `[SAS_TOKEN]` |
| Windows path username replaced | `"C:\Users\john.doe\file.log"` | `[USERNAME]` |
| Bearer token replaced | `"Bearer eyJhbGciOiJSUzI1NiJ9"` | `[TOKEN]` |
| Clean text unchanged | `"NullReferenceException in OrderService"` | same string |
| Multiple patterns in one string | email + IP in same message | both replaced |
| `scrub_dict` replaces nested string | `{"msg": "x@y.com", "count": 1}` | `{"msg": "[EMAIL]", "count": 1}` |
| `scrub_dict` handles list values | `{"frames": ["at x@y.com"]}` | `[EMAIL]` in list |
| Empty string safe | `""` | `""` |
| None-safe (via `or ""`) | upstream callers already guard; test `scrub("")` |

---

## Acceptance Criteria

- `ruff check .` passes with no warnings.
- `mypy apps/ packages/ --strict` passes with no issues.
- All unit tests in `test_pii_scrubber.py` pass.
- All existing 285 pipeline tests continue to pass (scrubbing must not break
  test fixtures — test LLM inputs do not contain real PII so scrubbing is a
  no-op for them).
- A manual review of `triage/agent.py`, `root_cause/agent.py`, and
  `fix_planner/agent.py` confirms `scrub()` is called on `exception_message`
  and `stack_trace` before `json.dumps`.

---

## Out of Scope for This Phase

- Scrubbing of content stored in PostgreSQL (historical data backfill).
- UI-level redaction in the React dashboard.
- Azure Purview integration.
- Custom allow-lists or tenant-configurable scrubbing rules.

These are candidates for a future security hardening phase.
