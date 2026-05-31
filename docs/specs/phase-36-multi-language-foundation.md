# Phase 36 — Multi-Language Foundation

## Goal

Make every language-specific decision in the agent pipeline pluggable so that
adding a new language (Python, Node.js, Java) requires only adding a new module
— not changing the pipeline, domain model, or agent contracts.

This phase does **not** add Python or Node.js ingestion (Phase 27 / 28). It
prepares the engine so those phases are purely additive. The visible runtime
behaviour after this phase is identical to before for .NET incidents.

---

## Problem This Solves

Several modules contain hardcoded .NET assumptions that must be touched every
time a new language is added:

| Module | Hardcoded assumption |
|---|---|
| `triage/rules.py` | Only .NET exception type patterns |
| `root_cause/stack_parser.py` | `_INTERNAL_PREFIXES` is .NET-only; Node.js/Java parsers missing |
| `code_context/frame_filter.py` | Duplicate .NET prefix list; no Python/Node.js/Java |
| `validation_agent/static_checks.py` | `.csproj` / `.sln` build file check |
| `domain/models/agent_state.py` | No `exception_language` field |
| `search/indexers/source_indexer.py` | `.cs` extension hardcoded |

Without this phase, each language-expansion phase (27, 28, Java future) must
edit existing modules, creating merge conflicts and regression risk.

---

## Deliverables

### 1. `exception_language` field in `IncidentState`

Add `exception_language: str | None` to `IncidentState`. The ingestion connector
sets it during incident creation by detecting the language from the exception type
and stack trace format. All agents read it to select the correct language-specific
behaviour.

Supported values: `"dotnet"` · `"python"` · `"nodejs"` · `"java"` · `"unknown"`

```python
exception_language: str | None  # dotnet | python | nodejs | java | unknown
```

### 2. Language detection utility

`packages/agent_runtime/language_detector.py` — pure function, no I/O:

```python
def detect_language(exception_type: str, stack_trace: str) -> str:
    """Return the most likely language tag from exception evidence."""
```

Detection heuristics (in order):

| Signal | Language |
|---|---|
| Stack contains `File "...py", line` | python |
| Stack contains `   at` + `.cs:line` | dotnet |
| Stack contains `   at` + `.js:` or `.ts:` | nodejs |
| Stack contains `at com.` / `at org.` / `.java:` | java |
| Exception type contains `System.` or ends in `Exception` (PascalCase, no dots) | dotnet |
| Exception type is lowercase or snake_case | python |
| Exception type is short camelCase with no dots | nodejs |
| Fallback | unknown |

### 3. Language-aware triage rule dispatch

Refactor `triage/rules.py`:

```python
# Before: one flat list
_RULES: list[TriageRule] = [...]

# After: per-language tables + dispatch
_RULES_BY_LANGUAGE: dict[str, list[TriageRule]] = {
    "dotnet": [...],   # existing rules, unchanged
    "python": [...],   # Phase 27 will fill; empty for now → LLM fallback
    "nodejs": [...],   # Phase 28 will fill; empty for now → LLM fallback
    "java":   [...],   # Future; empty for now → LLM fallback
}

def apply_rules(
    exception_type: str,
    exception_message: str,
    language: str,
) -> RuleMatch:
    rules = _RULES_BY_LANGUAGE.get(language, [])
    ...
```

### 4. Consolidated language-aware internal prefix filter

Create `packages/agent_runtime/language_internals.py`:

```python
FRAMEWORK_PREFIXES: dict[str, tuple[str, ...]] = {
    "dotnet": ("System.", "Microsoft.", "Azure.", "lambda_method"),
    "python": ("site-packages/", "lib/python", "<frozen ", "importlib"),
    "nodejs": ("node_modules/", "internal/", "<anonymous>"),
    "java":   ("java.", "javax.", "sun.", "com.sun.", "org.springframework."),
    "unknown": (),
}

def is_user_code(method_or_path: str, language: str) -> bool:
    prefixes = FRAMEWORK_PREFIXES.get(language, ())
    return not any(method_or_path.startswith(p) for p in prefixes)
```

Remove the duplicate `_INTERNAL_PREFIXES` lists from `stack_parser.py` and
`frame_filter.py`; both import from `language_internals`.

### 5. Node.js / V8 stack frame parser

Add `_try_parse_nodejs` to `root_cause/stack_parser.py`:

```python
# Format 1: at ClassName.method (/app/src/file.js:42:18)
# Format 2: at async handler (/app/src/routes/api.ts:42:18)
# Format 3: at /app/src/utils/helper.js:42:18 (anonymous)
_NODEJS_RE = re.compile(
    r"^\s*at\s+(?:async\s+)?(?P<method>\S+)\s+\((?P<path>[^)]+):(?P<line>\d+):\d+\)"
    r"|^\s*at\s+(?P<path2>[^:]+):(?P<line2>\d+):\d+"
)
```

### 6. Java stack frame parser

Add `_try_parse_java` to `root_cause/stack_parser.py`:

```python
# Format: at com.example.services.UserService.getById(UserService.java:42)
_JAVA_RE = re.compile(
    r"^\s*at\s+(?P<method>[\w.$]+)\((?P<file>[\w.]+):(?P<line>\d+)\)"
)
```

### 7. Language-aware build file checks in Validation Agent

Replace `.csproj` / `.sln` hardcoding in `validation_agent/static_checks.py`:

```python
BUILD_FILES_BY_LANGUAGE: dict[str, tuple[str, ...]] = {
    "dotnet": (".csproj", ".sln", ".targets", ".props"),
    "python": ("setup.py", "pyproject.toml", "requirements.txt", "setup.cfg"),
    "nodejs": ("package.json", "package-lock.json", "yarn.lock", "tsconfig.json"),
    "java":   ("pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle"),
    "unknown": (),
}
```

The check reads `exception_language` from the PR description or from the
`IncidentState` stored in the work item metadata.

### 8. Configurable source file extension in RAG indexer

Replace the `.cs` default in `packages/search/indexers/source_indexer.py`:

```python
# Before
async def list_files(self, path_prefix: str, extension: str = ".cs") -> list[str]:

# After — default comes from settings
async def list_files(
    self, path_prefix: str, extension: str | None = None
) -> list[str]:
    ext = extension or settings.source_file_extension or ".cs"
```

Add `source_file_extension: str = ".cs"` to `packages/config/settings.py`.

---

## `IncidentState` Changes

```python
# Add after exception_message field
exception_language: str | None  # set by ingestion; dotnet | python | nodejs | java | unknown
```

---

## Security Touchpoints

- No new LLM calls introduced.
- No new credentials or endpoints.
- `exception_language` is derived from ingested data — not user-controlled input
  after PII scrubbing; no scrubbing needed for this field itself.
- Language detection runs before any LLM call, so it cannot be prompt-injected.

---

## Files

```
New:
  packages/agent_runtime/language_detector.py   — detect_language()
  packages/agent_runtime/language_internals.py  — FRAMEWORK_PREFIXES, is_user_code()
  tests/unit/test_language_detector.py
  tests/unit/test_language_internals.py

Modified:
  packages/domain/models/agent_state.py         — add exception_language field
  packages/agent_runtime/triage/rules.py        — language dispatch
  packages/agent_runtime/root_cause/stack_parser.py — add nodejs + java parsers; use language_internals
  packages/agent_runtime/code_context/frame_filter.py — use language_internals
  packages/agent_runtime/validation_agent/static_checks.py — language-aware build file check
  packages/search/indexers/source_indexer.py    — configurable extension
  packages/config/settings.py                  — add source_file_extension
  apps/worker/ingestion/connector.py            — set exception_language on new incidents
```

---

## Acceptance Criteria

- `ruff check .` and `mypy apps/ packages/ --strict` pass.
- All existing tests continue to pass — .NET incident processing is unaffected.
- `detect_language("NullReferenceException", dotnet_trace)` returns `"dotnet"`.
- `detect_language("AttributeError", python_trace)` returns `"python"`.
- `detect_language("TypeError", nodejs_trace)` returns `"nodejs"`.
- `detect_language("NullPointerException", java_trace)` returns `"java"`.
- `_INTERNAL_PREFIXES` no longer exists in `stack_parser.py` or `frame_filter.py`.
- Triage agent uses `exception_language` to select the rule table.
- Validation agent uses language-aware build file patterns.
- New incidents created by the ingestion connector have `exception_language` set.

---

## Out of Scope

- Python ingestion connector (Phase 27).
- Node.js ingestion connector (Phase 28).
- Java ingestion connector (future).
- Language-specific LLM prompts (Phase 27+).
- GitHub source control (Phase 38).
