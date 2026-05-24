# Phase 30 — Python Application Exception Support

## Goal

Extend the ingestion and triage pipeline to handle Python application
exceptions (tracebacks) in addition to .NET and Node.js exceptions.

---

## Background

Follows the same extension pattern established in Phase 29.  Python tracebacks
have a distinct format — they unwind bottom-up rather than top-down, and the
exception type is separated from the traceback by a blank line.

---

## Deliverables

| Artifact | Description |
|---|---|
| `packages/parsers/python_stack_parser.py` | Parse Python traceback format into `StackFrame` list |
| Updated `packages/parsers/parser_registry.py` | Add `"python"` case |
| Updated `packages/domain/models/agent_state.py` | `exception_source` now supports `"python"` |
| Updated `packages/agent_runtime/triage/rules.py` | Python-specific triage rules |
| `docs/prompts/triage_v4.md` | Triage prompt aware of Python; updated label taxonomy |
| `docs/prompts/root_cause_v4.md` | Root cause prompt adapted for Python traceback format |
| `tests/unit/test_python_parser.py` | Unit tests: parse real Python tracebacks |
| Updated `tests/unit/test_triage_rules.py` | Python rule coverage |
| Updated agent eval fixtures | `python_key_error.json`, `python_attribute_error.json` |

---

## Python Traceback Format

```
Traceback (most recent call last):
  File "/app/services/order_service.py", line 88, in checkout
    user = self.user_repo.get(order.user_id)
  File "/app/repositories/user_repository.py", line 42, in get
    return self.db.query(User).filter(User.id == user_id).one()
sqlalchemy.orm.exc.NoResultFound: No row was found when one was required
```

Key differences from .NET and Node.js:
- Stack unwinds **bottom-up** (last line is the innermost frame).
- Frame format: `File "{path}", line {n}, in {function}`.
- The exception type and message appear on the **last line**, not the first.
- Exception type may include a module prefix: `sqlalchemy.orm.exc.NoResultFound`.
- Multi-exception chains use `During handling of the above exception, another exception occurred:`.

---

## Python Stack Parser

The parser must:
1. Detect the traceback header (`"Traceback (most recent call last):"`).
2. Extract frames in order (preserving bottom-up order).
3. Identify `exception_type` from the final line before the message.
4. Handle chained exceptions (`__cause__` and `__context__` chains).
5. Mark frames from `site-packages/` as `is_framework = True`.

---

## `exception_source` Detection

Extension to the heuristic introduced in Phase 29:

```python
def detect_exception_source(payload: dict) -> str:
    stack = payload.get("stack_trace", "") or ""
    if "Traceback (most recent call last)" in stack:
        return "python"
    if "at " in stack and ("node_modules" in stack or ".js:" in stack):
        return "nodejs"
    return "dotnet"
```

---

## Triage Rules — Python Additions

| Exception Type / Pattern | Priority | Labels |
|---|---|---|
| `AttributeError: 'NoneType' object has no attribute` | high | `null-reference`, `python` |
| `KeyError` | medium | `key-not-found`, `python` |
| `IndexError` | medium | `index-out-of-bounds`, `python` |
| `MemoryError` | critical | `resource-exhaustion`, `python` |
| `RecursionError` | high | `stack-overflow`, `python` |
| `ConnectionRefusedError` | medium | `connection-failure`, `python` |
| `TimeoutError` | medium | `timeout`, `python` |
| `sqlalchemy.orm.exc.NoResultFound` | medium | `not-found`, `python`, `database` |
| `django.core.exceptions.ObjectDoesNotExist` | medium | `not-found`, `python`, `django` |
| `jwt.exceptions.InvalidTokenError` | medium | `authentication`, `python` |

---

## Agent Eval Fixtures

### `python_key_error.json`

```json
{
  "incident_id": "eval-python-001",
  "exception_source": "python",
  "exception_type": "KeyError",
  "exception_message": "'user_id'",
  "stack_trace": "Traceback (most recent call last):\n  File \"/app/services/order_service.py\", line 88, in checkout\n    user = session['user_id']\nKeyError: 'user_id'",
  "expected": {
    "priority": "medium",
    "triage_labels_contains": ["key-not-found", "python"],
    "triage_rule_matched": true
  }
}
```

### `python_attribute_error.json`

```json
{
  "incident_id": "eval-python-002",
  "exception_source": "python",
  "exception_type": "AttributeError",
  "exception_message": "'NoneType' object has no attribute 'email'",
  "stack_trace": "Traceback (most recent call last):\n  File \"/app/api/views.py\", line 34, in get_user\n    return user.email\nAttributeError: 'NoneType' object has no attribute 'email'",
  "expected": {
    "priority": "high",
    "triage_labels_contains": ["null-reference", "python"],
    "triage_rule_matched": true
  }
}
```

---

## Acceptance Criteria

- `ruff check .` and `mypy apps/ packages/ --strict` pass.
- Python traceback fixtures produce correct priority and labels.
- `site-packages/` frames are marked `is_framework = True`.
- Chained exceptions are parsed without error (the outer exception is used).
- Existing .NET and Node.js tests continue to pass.
- `test_python_parser.py` covers: simple traceback, chained exception,
  framework-only frames, multi-line exception message.

---

## Out of Scope

- Celery task traceback format (deferred).
- Asyncio task exception wrappers (deferred).
- Python source code context via ADO Repos (assumes Python repos are also
  in ADO; code context agent already handles arbitrary file paths).
